"""Command-line interface for TotalSync decoder."""

import argparse
import os
import sys
import numpy as np
from scipy.io import savemat
from .decoder import decode_b64_files


def save_as_npy(data_dict, output_dir, base_name):
    """Save decoded data as .npy files."""
    output_path = os.path.join(output_dir, f"{base_name}_decoded.npy")
    np.save(output_path, data_dict)
    print(f"Saved: {output_path}")


def save_as_mat(data_dict, output_dir, base_name):
    """Save decoded data as .mat file."""
    output_path = os.path.join(output_dir, f"{base_name}_decoded.mat")
    savemat(output_path, data_dict)
    print(f"Saved: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Decode TotalSync .b64 files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decode files and print to console
  totalsync-decode /path/to/data

  # Save as .mat files
  totalsync-decode /path/to/data --output /path/to/output --format mat

  # Save as .npy files
  totalsync-decode /path/to/data --output /path/to/output --format npy

  # Use pin mapping to split channels by name
  totalsync-decode /path/to/data --output /path/to/output --pin-json docs/pinSheet.json
        """
    )

    parser.add_argument(
        'directory',
        help='Directory containing .b64 files to decode'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output directory (if not specified, data is only returned, not saved)',
        default=None
    )

    parser.add_argument(
        '-f', '--format',
        choices=['npy', 'mat'],
        default='mat',
        help='Output format for saved files (default: mat)'
    )

    parser.add_argument(
        '-p', '--pin-json',
        help='Path to pin mapping JSON file (e.g., pinSheet.json)',
        default=None
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Check input directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        return 1

    # Create output directory if specified
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        if not os.path.isdir(args.output):
            print(f"Error: Could not create output directory: {args.output}", file=sys.stderr)
            return 1

    # Check pin JSON file if provided
    if args.pin_json and not os.path.isfile(args.pin_json):
        print(f"Error: Pin JSON file not found: {args.pin_json}", file=sys.stderr)
        return 1

    # Decode files
    try:
        results = decode_b64_files(args.directory, verbose=not args.quiet, pin_json_path=args.pin_json)
    except Exception as e:
        print(f"Error during decoding: {e}", file=sys.stderr)
        return 1

    # Save results if output directory specified
    if args.output:
        for name, data in results.items():
            if args.format == 'npy':
                save_as_npy(data, args.output, name)
            else:  # mat
                save_as_mat(data, args.output, name)
    else:
        if not args.quiet:
            print(f"\nDecoded {len(results)} file(s)")
            print("No output directory specified - data not saved")

    return 0


if __name__ == '__main__':
    sys.exit(main())
