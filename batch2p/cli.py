#!/usr/bin/env python3
"""
Batch 2-photon preprocessing – CLI entry point.

Usage:
    batch2p <data_suite3d.json> [--working-dir <dir>]

The data JSON file must contain a "source_extraction" field specifying the
algorithm (e.g. "suite3d"). Synchronization is handled generically and depends
only on the original TIF and .b64 files.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# os.chdir(os.path.dirname(os.path.abspath("")))

from totalsync_2p.sync import synchronize
from batch2p.extractors import get_extractor


class TeeStream:
    """Write to both a stream and a file simultaneously."""
    def __init__(self, stream, file):
        self.stream = stream
        self.file = file

    def write(self, data):
        self.stream.write(data)
        self.file.write(data)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def fileno(self):
        return self.stream.fileno()


def collect_tifs(data: dict) -> list[Path]:
    root = Path(data["root_path"]) if "root_path" in data else Path(".")
    tifs = []
    for item in data["data"]:
        p = root / item
        if p.suffix.lower() in (".tif", ".tiff"):
            tifs.append(p)
        elif p.is_dir():
            tifs.extend(sorted(p.glob("*.tif")) + sorted(p.glob("*.tiff")))
        else:
            raise TypeError(f"Unexpected file type: {p}")
    return tifs


def split_tifs(tifs: list[Path], chunk_size: int, tmp_dir: Path,
               block_size: int = 3, add_offset: bool = False) -> list[Path]:
    from tifftrim.trim import split_3d_tiff_into_chunks
    split = []
    for tif in tifs:
        chunks = split_3d_tiff_into_chunks(
            tif, tmp_dir, chunk_size,
            block_size=block_size,
            add_offset=add_offset,
        )
        split.extend(chunks)
    return split


def collect_b64s(data: dict) -> list[Path]:
    root = Path(data["root_path"]) if "root_path" in data else Path(".")
    b64s = []
    for item in data["behavior_data"]:
        p = root / item
        if p.suffix.lower() != ".b64":
            raise TypeError(f"Expected a .b64 file in behavior_data, got: {p}")
        b64s.append(p)
    return b64s


def copy_files_to_working_dir(files: list[Path], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in files:
        dest = dest_dir / f.name
        print(f"  {f} -> {dest}")
        shutil.copy2(f, dest)
        copied.append(dest)
    return copied


def main():
    parser = argparse.ArgumentParser(description="Batch 2-photon preprocessing")
    parser.add_argument("data_json", type=Path, help="Path to data JSON file")
    parser.add_argument("--working-dir", type=Path, default=None,
                        help="Local scratch directory. Input files are copied here; "
                             "results are copied back to their original destinations on completion.")
    parser.add_argument("--debug", action="store_true",
                        help="Debug mode: skip cleanup of temp/working directories on error.")
    parser.add_argument("--sync_only", action="store_true",
                        help="Skip source extraction; assume results already exist and only run synchronization.")
    args = parser.parse_args()
    sync_only = args.sync_only

    with open(args.data_json) as f:
        data = json.load(f)

    algorithm = data.get("source_extraction", "suite3d")
    extractor = get_extractor(algorithm, data)

    job_id = data["job_id"]
    original_job_root_dir = Path(data["job_root_dir"])
    original_results_root_dir = Path(data.get("results_root_dir",
                                               str(original_job_root_dir / "results")))
    original_results_path = original_results_root_dir / job_id

    fill_tsync_gaps = bool(data.get("fill_tsync_gaps", False))
    block_size = int(data.get("block_size", 3))
    working_dir_base = args.working_dir or (Path(data["working_dir"]) if "working_dir" in data else None)

    if working_dir_base is not None:
        working_dir_base.mkdir(parents=True, exist_ok=True)
        working_dir = Path(tempfile.mkdtemp(prefix=f"batch2p_{job_id}_", dir=working_dir_base))
    else:
        working_dir = None

    tifs = collect_tifs(data)
    original_tifs = tifs
    print("Input files:")
    for t in tifs:
        print(f"  {t}")

    has_behavior = "behavior_data" in data
    if has_behavior:
        b64_files = collect_b64s(data)
        if len(b64_files) != len(original_tifs):
            raise ValueError(
                f"behavior_data has {len(b64_files)} entries but data has "
                f"{len(original_tifs)} tif files; counts must match."
            )
        pinsheet_file = Path(data["pinsheet_file"])
        if not pinsheet_file.is_absolute():
            root = Path(data["root_path"]) if "root_path" in data else Path(".")
            pinsheet_file = root / pinsheet_file
    else:
        b64_files = []
        pinsheet_file = None

    if working_dir is not None:
        job_root_dir = working_dir / original_job_root_dir.name
        results_root_dir = working_dir / original_results_root_dir.name
    else:
        job_root_dir = original_job_root_dir
        results_root_dir = original_results_root_dir

    results_path = results_root_dir / job_id
    results_path.mkdir(parents=True, exist_ok=True)

    log_path = results_path / f"{job_id}.log"
    log_file = open(log_path, "w", buffering=1)  # line-buffered
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(original_stdout, log_file)
    sys.stderr = TeeStream(original_stderr, log_file)

    tmp_dir = None
    _exception_raised = False
    try:
        if sync_only:
            if not original_results_path.exists():
                raise FileNotFoundError(
                    f"--sync_only: no existing results found at {original_results_path}"
                )
            if working_dir is not None:
                print(f"\nSession temp directory: {working_dir}")
                print(f"Copying existing results to working directory: {results_path} ...")
                for item in original_results_path.iterdir():
                    if item.suffix == ".log":
                        continue
                    dest = results_path / item.name
                    if item.is_dir():
                        shutil.copytree(str(item), str(dest))
                    else:
                        shutil.copy2(str(item), str(dest))
                print("Done copying.")
        else:
            if working_dir is not None:
                print(f"\nSession temp directory: {working_dir}")
                print("Copying input files to working directory...")
                tifs = copy_files_to_working_dir(tifs, working_dir / "input_tifs")
                if has_behavior:
                    b64_files = copy_files_to_working_dir(b64_files, working_dir / "input_b64s")
                print("Done copying.")

        # Save pre-split tif paths for behavioral sync (b64 files are per-session, not per-chunk)
        tifs_for_sync = list(tifs)

        if not sync_only:
            chunk_size = int(data.get("tiff_trim_size", 0))
            if chunk_size:
                if working_dir is not None:
                    tmp_dir = working_dir / "split_tifs"
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                else:
                    tmp_parent = Path(data["temp_dir"]) if "temp_dir" in data else None
                    if tmp_parent is not None:
                        tmp_parent.mkdir(parents=True, exist_ok=True)
                    tmp_dir = Path(tempfile.mkdtemp(prefix="batch2p_", dir=tmp_parent))
                print(f"\nSplitting TIFFs into chunks of {chunk_size} frames -> {tmp_dir}")
                add_offset = bool(data.get("add_offset", False))
                tifs = split_tifs(tifs, chunk_size, tmp_dir, block_size=block_size, add_offset=add_offset)
                print("Split files:")
                for t in tifs:
                    print(f"  {t}")

            # When a working directory is used, let the extractor know so it can place
            # any algorithm-level scratch files (e.g. suite2p fast_disk) there.
            if working_dir is not None:
                data["temp_dir"] = str(working_dir)

            # Save reproducibility files
            extractor.save_reproducibility_info(results_path)

            saved_data = dict(data)
            saved_data["data"] = [str(t) for t in original_tifs]
            saved_data.pop("root_path", None)
            saved_data["results_root_dir"] = str(original_results_root_dir)
            saved_data["job_root_dir"] = str(original_job_root_dir)
            with open(results_path / "data_used.json", "w") as f:
                json.dump(saved_data, f, indent=2)

            # Run source extraction
            extractor.run(tifs, job_root_dir, job_id, results_path)

        if has_behavior:
            print("\nRunning behavioral synchronization...")
            behavior_sync_dir = results_root_dir / "behavior_sync"
            behavior_sync_dir.mkdir(parents=True, exist_ok=True)
            sync_results = []
            for tif, b64 in zip(tifs_for_sync, b64_files):
                print(f"  Synchronizing {tif.name} + {b64.name}")
                stats = synchronize(str(tif), str(b64), str(behavior_sync_dir), str(pinsheet_file),
                                    fill_gaps=fill_tsync_gaps)
                sync_results.append(stats)
            print("Behavioral synchronization done.")

            print(f"\nCreating behavior-synced {algorithm} outputs...")
            extractor.create_synced_outputs(
                tif_files=tifs_for_sync,
                sync_results=sync_results,
                results_path=results_path,
                behavior_sync_dir=behavior_sync_dir,
                block_size=block_size,
            )
            print("Synced outputs done.")

    except Exception:
        _exception_raised = True
        raise
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.flush()
        log_file.close()

        skip_cleanup = args.debug and _exception_raised

        if tmp_dir is not None and tmp_dir.exists() and working_dir is None:
            if skip_cleanup:
                print(f"\n[debug] Keeping temporary directory on error: {tmp_dir}")
            else:
                shutil.rmtree(tmp_dir)
                print(f"\nCleaned up temporary directory: {tmp_dir}")

        if working_dir is not None and working_dir.exists():
            if skip_cleanup:
                print(f"\n[debug] Keeping session temp directory on error: {working_dir}")
            else:
                try:
                    print(f"\nCopying results back to {original_results_path} ...")
                    if original_results_path.exists():
                        shutil.rmtree(original_results_path)
                    original_results_root_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(results_path), str(original_results_path))

                    job_subdir = extractor.get_job_subdir(job_id)
                    working_job_path = job_root_dir / job_subdir
                    original_job_path = original_job_root_dir / job_subdir
                    if working_job_path.exists():
                        print(f"Copying job directory back to {original_job_path} ...")
                        if original_job_path.exists():
                            shutil.rmtree(original_job_path)
                        if original_job_root_dir.exists() and not original_job_root_dir.is_dir():
                            raise RuntimeError(
                                f"Cannot create job root directory: {original_job_root_dir} "
                                f"already exists as a non-directory file. "
                                f"Remove or rename it and retry."
                            )
                        original_job_root_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(str(working_job_path), str(original_job_path))

                    if has_behavior:
                        working_behavior_sync = results_root_dir / "behavior_sync"
                        original_behavior_sync = original_results_root_dir / "behavior_sync"
                        if working_behavior_sync.exists():
                            print(f"Copying behavior_sync back to {original_behavior_sync} ...")
                            if original_behavior_sync.exists():
                                shutil.rmtree(original_behavior_sync)
                            original_results_root_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(str(working_behavior_sync), str(original_behavior_sync))

                    print(f"Cleaning up session temp directory: {working_dir} ...")
                    shutil.rmtree(working_dir)
                    print("Done.")
                except Exception as copy_err:
                    if _exception_raised:
                        print(f"\nWARNING: copy-back failed ({type(copy_err).__name__}: {copy_err}); "
                              f"working directory preserved at: {working_dir}", file=sys.stderr)
                    else:
                        raise


if __name__ == "__main__":
    main()
