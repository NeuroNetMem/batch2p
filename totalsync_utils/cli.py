"""Command-line interface for TotalSync decoder."""

import argparse
import os
import re
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.io import savemat

from .decoder import decode_b64_files


def _fix_tsync_time(log_times: np.ndarray) -> np.ndarray:
    skips = -np.where(
        np.diff(log_times) < 0,
        np.diff(log_times) - np.median(np.diff(log_times)),
        0,
    )
    cs = np.cumsum(skips)
    return log_times + np.hstack((0, cs))


def _normalize_underscores(s: str) -> str:
    return re.sub(r'_+', '_', s).rstrip('_')


def save_as_pynapple(data_dict, output_dir, base_name):
    """Save decoded b64 data as pynapple Tsd/TsdFrame files, time-indexed by corrected TotalSync clock."""
    import pynapple as nap

    log_times = data_dict['startTS'].astype(int)
    tsync_time = _fix_tsync_time(log_times)

    gap_locations = tsync_time[np.where(np.diff(log_times) > 30000)]
    if len(gap_locations) > 0:
        warnings.warn(f"{base_name}: gaps in timestamps at {gap_locations}")

    behavior_dir = Path(output_dir) / base_name / "behavior"
    behavior_dir.mkdir(parents=True, exist_ok=True)

    for key, arr in data_dict.items():
        if not isinstance(arr, np.ndarray):
            continue
        key_name = _normalize_underscores(
            key.replace(" ", "_").replace("(", "_").replace(")", "_").replace("-", "_")
        )
        if arr.ndim == 1 and len(arr) == len(tsync_time):
            nap.Tsd(t=tsync_time, d=arr, time_units='us').save(behavior_dir / f"{key_name}.npz")
        elif arr.ndim == 2 and arr.shape[0] == len(tsync_time):
            nap.TsdFrame(t=tsync_time, d=arr, time_units='us').save(behavior_dir / f"{key_name}.npz")

    print(f"Saved: {behavior_dir}")


def save_as_pynapple_concatenated(results_dict, output_dir):
    """Concatenate multiple decoded b64 files into a single set of pynapple files.

    Timestamps are shifted so each file's time axis starts at prev_end + 1 (in µs).
    """
    import pynapple as nap

    all_tsync_times = []
    offset = None
    for name, data_dict in results_dict.items():
        log_times = data_dict['startTS'].astype(int)
        tsync_time = _fix_tsync_time(log_times)

        gap_locations = tsync_time[np.where(np.diff(log_times) > 30000)]
        if len(gap_locations) > 0:
            warnings.warn(f"{name}: gaps in timestamps at {gap_locations}")

        if offset is None:
            shifted = tsync_time
        else:
            shifted = tsync_time - tsync_time[0] + offset + 1

        all_tsync_times.append(shifted)
        offset = int(shifted[-1])

    tsync_time_cat = np.concatenate(all_tsync_times)

    behavior_dir = Path(output_dir) / "behavior"
    behavior_dir.mkdir(parents=True, exist_ok=True)

    first_data = next(iter(results_dict.values()))
    for key in first_data:
        arrays = [d[key] for d in results_dict.values()
                  if key in d and isinstance(d[key], np.ndarray)]
        if len(arrays) != len(results_dict):
            continue

        arr = np.concatenate(arrays, axis=0)
        key_name = _normalize_underscores(
            key.replace(" ", "_").replace("(", "_").replace(")", "_").replace("-", "_")
        )
        if arr.ndim == 1 and len(arr) == len(tsync_time_cat):
            nap.Tsd(t=tsync_time_cat, d=arr, time_units='us').save(behavior_dir / f"{key_name}.npz")
        elif arr.ndim == 2 and arr.shape[0] == len(tsync_time_cat):
            nap.TsdFrame(t=tsync_time_cat, d=arr, time_units='us').save(behavior_dir / f"{key_name}.npz")

    print(f"Saved concatenated pynapple files to: {behavior_dir}")


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

  # Save as pynapple Tsd/TsdFrame files (time-indexed by TotalSync clock)
  totalsync-decode /path/to/data --output /path/to/output --format pynapple --pin-json docs/pinSheet.json

  # Concatenate multiple b64 files into a single set of pynapple files
  totalsync-decode /path/to/data --output /path/to/output --format pynapple --concatenate --pin-json docs/pinSheet.json
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
        choices=['npy', 'mat', 'pynapple'],
        default='mat',
        help='Output format for saved files (default: mat)'
    )

    parser.add_argument(
        '-p', '--pin-json',
        help='Path to pin mapping JSON file (e.g., pinSheet.json)',
        default=None
    )

    parser.add_argument(
        '--concatenate',
        action='store_true',
        help='Concatenate all b64 files into a single set of pynapple files (only with --format pynapple)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    if args.concatenate and args.format != 'pynapple':
        print("Error: --concatenate is only valid with --format pynapple", file=sys.stderr)
        return 1

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
        if args.format == 'pynapple' and args.concatenate:
            save_as_pynapple_concatenated(results, args.output)
        else:
            for name, data in results.items():
                if args.format == 'npy':
                    save_as_npy(data, args.output, name)
                elif args.format == 'pynapple':
                    save_as_pynapple(data, args.output, name)
                else:  # mat
                    save_as_mat(data, args.output, name)
    else:
        if not args.quiet:
            print(f"\nDecoded {len(results)} file(s)")
            print("No output directory specified - data not saved")

    return 0


if __name__ == '__main__':
    sys.exit(main())
