"""Command-line interface for totalsync_2p."""

import argparse
import sys

from .sync import synchronize


def main():
    parser = argparse.ArgumentParser(
        description='Synchronize ScanImage tif recordings with TotalSync behavioral telemetry.'
    )

    input_group = parser.add_argument_group('input files')
    input_group.add_argument(
        '--tif-files',
        nargs='+',
        metavar='TIF',
        help='One or more ScanImage tif files.',
    )
    input_group.add_argument(
        '--b64-files',
        nargs='+',
        metavar='B64',
        help='One or more TotalSync .b64 files, in the same order as --tif-files.',
    )

    parser.add_argument(
        '--output-dir',
        required=True,
        metavar='DIR',
        help='Directory where output files will be saved.',
    )
    parser.add_argument(
        '--pin-sheet',
        required=True,
        metavar='JSON',
        help='Path to the pin mapping JSON file.',
    )

    args = parser.parse_args()

    if not args.tif_files or not args.b64_files:
        parser.error('--tif-files and --b64-files are required.')

    if len(args.tif_files) != len(args.b64_files):
        parser.error(
            f'Number of tif files ({len(args.tif_files)}) must match '
            f'number of b64 files ({len(args.b64_files)}).'
        )

    errors = []
    for i, (tif, b64) in enumerate(zip(args.tif_files, args.b64_files)):
        print(f'\n[{i + 1}/{len(args.tif_files)}] Processing {tif} + {b64}')
        try:
            stats = synchronize(
                tif_file=tif,
                b64_file=b64,
                output_dir=args.output_dir,
                pin_sheet_file=args.pin_sheet,
            )
            barcode_info = 'barcode' if stats['has_barcode'] else 'no barcode (clock-based)'
            print(f'  Done — session: {stats["session"]}, alignment: {barcode_info}')
        except Exception as e:
            print(f'  ERROR: {e}', file=sys.stderr)
            errors.append((tif, b64, e))

    if errors:
        print(f'\n{len(errors)} file(s) failed:', file=sys.stderr)
        for tif, b64, e in errors:
            print(f'  {tif} / {b64}: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
