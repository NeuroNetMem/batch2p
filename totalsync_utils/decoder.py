"""Decode TotalSync .b64 files."""

import os
import glob
import json
import struct
import base64
import numpy as np
from collections import namedtuple
from cobs import cobs
from tqdm import tqdm


# Format package
DataPacketDesc = {
    'type': 'B',
    'size': 'B',
    'crc16': 'H',
    'packetID': 'I',
    'us_start': 'I',
    'us_end': 'I',
    'analog': '8H',
    'states': '8l',
    'digitalIn': '2H',
    'digitalOut': '3B',
    'padding': 'x'
}

DataPacket = namedtuple('DataPacket', DataPacketDesc.keys())
DataPacketStruct = '<' + ''.join(DataPacketDesc.values())
DataPacketSize = struct.calcsize(DataPacketStruct)

# Package with non-digital data
dtype_no_digital = [
    ('type', np.uint8),
    ('size', np.uint8),
    ('crc16', np.uint16),
    ('packetID', np.uint32),
    ('us_start', np.uint32),
    ('us_end', np.uint32),
    ('analog', np.uint16, (8,)),
    ('states', np.uint32, (8,))
]

# DigitalIn and DigitalOut
dtype_w_digital = dtype_no_digital + [
    ('digital_in', np.uint16, (16,)),
    ('digital_out', np.uint16, (16,))
]

# Creating array with all the data
np_DataPacketType_noDigital = np.dtype(dtype_no_digital)
np_DataPacketType_withDigital = np.dtype(dtype_w_digital)


def count_lines(fp):
    """Count the number of lines in a file."""
    def _make_gen(reader):
        b = reader(2**17)
        while b:
            yield b
            b = reader(2**17)

    with open(fp, 'rb') as f:
        count = sum(buf.count(b'\n') for buf in _make_gen(f.raw.read))
    return count


def unpack_data_packet(dp):
    """Unpack a data packet."""
    s = struct.unpack(DataPacketStruct, dp)
    up = DataPacket(
        type=s[0], size=s[1], crc16=s[2], packetID=s[3],
        us_start=s[4], us_end=s[5], analog=s[6:14], states=s[14:22],
        digitalIn=s[22], digitalOut=s[23], padding=None
    )
    return up


def load_pin_mapping(pin_json_path):
    """
    Load pin mapping from JSON file.

    Parameters
    ----------
    pin_json_path : str
        Path to the pin mapping JSON file

    Returns
    -------
    dict
        Dictionary with keys 'digital_in', 'digital_out', 'analog_in' mapping
        indices to pin names (from the 'for' field)
    """
    with open(pin_json_path, 'r') as f:
        pin_data = json.load(f)

    mapping = {
        'digital_in': {},
        'digital_out': {},
        'analog_in': {}
    }

    for pin in pin_data['pins']:
        name = pin['name']
        for_field = pin.get('for')

        # Skip pins without a 'for' field or not used
        if not for_field or not pin.get('used', False):
            continue

        if name.startswith('digital_input_'):
            idx = int(name.split('_')[-1])
            mapping['digital_in'][idx] = for_field
        elif name.startswith('digital_output_'):
            idx = int(name.split('_')[-1])
            mapping['digital_out'][idx] = for_field
        elif name.startswith('analog_input_'):
            idx = int(name.split('_')[-1])
            mapping['analog_in'][idx] = for_field

    return mapping


def apply_pin_mapping(decoded_data, pin_mapping):
    """
    Apply pin mapping to decoded data, splitting channels by name.

    Parameters
    ----------
    decoded_data : dict
        Decoded data dictionary with raw arrays
    pin_mapping : dict
        Pin mapping from load_pin_mapping()

    Returns
    -------
    dict
        Dictionary with individual channels split out by name
    """
    result = {
        'startTS': decoded_data['startTS'],
        'transmitTS': decoded_data['transmitTS'],
        'longVar': decoded_data['longVar'],
        'packetNums': decoded_data['packetNums']
    }

    # Map digital inputs
    if pin_mapping['digital_in']:
        for idx, name in pin_mapping['digital_in'].items():
            result[name] = decoded_data['digitalIn'][:, idx]

    # Map digital outputs
    if pin_mapping['digital_out']:
        for idx, name in pin_mapping['digital_out'].items():
            result[name] = decoded_data['digitalOut'][:, idx]

    # Map analog inputs
    if pin_mapping['analog_in']:
        for idx, name in pin_mapping['analog_in'].items():
            result[name] = decoded_data['analog'][:, idx]

    # Keep original arrays if no mapping was applied
    if not pin_mapping['digital_in']:
        result['digitalIn'] = decoded_data['digitalIn']
    if not pin_mapping['digital_out']:
        result['digitalOut'] = decoded_data['digitalOut']
    if not pin_mapping['analog_in']:
        result['analog'] = decoded_data['analog']

    return result


def decode_single_file(file_path, verbose=True, pin_json_path=None):
    """
    Decode a single .b64 file.

    Parameters
    ----------
    file_path : str
        Path to the .b64 file
    verbose : bool
        Whether to print progress information
    pin_json_path : str, optional
        Path to pin mapping JSON file. If provided, splits channels by name.

    Returns
    -------
    dict
        Dictionary containing decoded data with keys:
        - analog: analog inputs (n_packets x 8) [if no pin mapping]
        - digitalIn: digital inputs (n_packets x 16) [if no pin mapping]
        - digitalOut: digital outputs (n_packets x 16) [if no pin mapping]
        - startTS: start timestamps (n_packets)
        - transmitTS: transmission timestamps (n_packets)
        - longVar: state variables (n_packets x 8)
        - packetNums: packet numbers (n_packets)

        If pin_json_path is provided, individual channels are split out
        with keys from the 'for' field in the JSON.
    """
    num_lines = count_lines(file_path)
    log_duration = num_lines / 1000 / 60

    if verbose:
        print(f'{file_path}')
        print(f'{num_lines} packets, ~{log_duration:0.2f} minutes')

    # Decode and create new dataset
    data = np.zeros(num_lines, dtype=np_DataPacketType_withDigital)
    non_digital_names = list(np_DataPacketType_noDigital.names)

    with open(file_path, 'rb') as bf:
        iterator = tqdm(bf, total=num_lines) if verbose else bf
        for nline, line in enumerate(iterator):
            bl = cobs.decode(base64.b64decode(line[:-1])[:-1])
            dp = unpack_data_packet(bl)
            data[non_digital_names][nline] = np.frombuffer(bl[:-8], dtype=np_DataPacketType_noDigital)
            digital_arr = np.frombuffer(bl[-8:], dtype=np.uint8)
            data[nline]['digital_in'] = np.hstack([
                np.unpackbits(digital_arr[1]),
                np.unpackbits(digital_arr[0])
            ])
            data[nline]['digital_out'] = np.hstack([
                np.unpackbits(digital_arr[3]),
                np.unpackbits(digital_arr[2])
            ])

    # Check for packetID jumps
    jumps = np.unique(np.diff(data['packetID']))

    # Flip digital arrays
    data['digital_in'] = np.flip(data['digital_in'], 1)
    data['digital_out'] = np.flip(data['digital_out'], 1)

    # Create output dictionary
    decoded = {
        "analog": data['analog'],
        "digitalIn": data['digital_in'],
        "digitalOut": data['digital_out'],
        "startTS": data['us_start'],
        "transmitTS": data['us_end'],
        "longVar": data['states'],
        "packetNums": data['packetID']
    }

    # Apply pin mapping if provided
    if pin_json_path:
        pin_mapping = load_pin_mapping(pin_json_path)
        decoded = apply_pin_mapping(decoded, pin_mapping)

    return decoded


def decode_b64_files(directory, verbose=True, pin_json_path=None):
    """
    Decode all .b64 files in a directory.

    Parameters
    ----------
    directory : str
        Path to directory containing .b64 files
    verbose : bool
        Whether to print progress information
    pin_json_path : str, optional
        Path to pin mapping JSON file. If provided, splits channels by name.

    Returns
    -------
    dict
        Dictionary mapping filenames (without extension) to decoded data
    """
    b64_files = glob.glob(os.path.join(directory, '*.b64'))

    if not b64_files:
        raise ValueError(f"No .b64 files found in {directory}")

    results = {}

    for file_path in b64_files:
        filename = os.path.basename(file_path)
        name = os.path.splitext(filename)[0]

        if verbose:
            print(f"\nProcessing {filename}...")

        decoded = decode_single_file(file_path, verbose=verbose, pin_json_path=pin_json_path)
        results[name] = decoded

    return results
