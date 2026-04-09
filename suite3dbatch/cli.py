#!/usr/bin/env python3
"""
Batch suite3d preprocessing – CLI entry point.

Usage:
    suite3dbatch <data.json> [--working-dir <dir>]

The data JSON file must contain a "params_file" key pointing to the params JSON.
If "params_file" is a relative path it is resolved relative to "root_path".
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

os.chdir(os.path.dirname(os.path.abspath("")))

from suite3d.job import Job
from suite3d import io


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


def load_params(params_path: Path) -> dict:
    with open(params_path) as f:
        params = json.load(f)
    # Convert lists that must be np.arrays
    if "planes" in params:
        params["planes"] = np.array(params["planes"])
    return params


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


def params_to_json_serializable(params: dict) -> dict:
    out = {}
    for k, v in params.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        else:
            out[k] = v
    return out


def copy_tifs_to_working_dir(tifs: list[Path], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for tif in tifs:
        dest = dest_dir / tif.name
        print(f"  {tif} -> {dest}")
        shutil.copy2(tif, dest)
        copied.append(dest)
    return copied


def main():
    parser = argparse.ArgumentParser(description="Batch suite3d preprocessing")
    parser.add_argument("data_json", type=Path, help="Path to data JSON file")
    parser.add_argument("--working-dir", type=Path, default=None,
                        help="Local scratch directory. Input files are copied here; "
                             "results are copied back to their original destinations on completion.")
    args = parser.parse_args()

    with open(args.data_json) as f:
        data = json.load(f)

    # Resolve params_file: relative paths are anchored to root_path
    params_file = Path(data["params_file"])
    if not params_file.is_absolute():
        root = Path(data["root_path"]) if "root_path" in data else Path(".")
        params_file = root / params_file

    params = load_params(params_file)

    job_id = data["job_id"]
    original_job_root_dir = Path(data["job_root_dir"])
    original_results_root_dir = Path(data.get("results_root_dir",
                                               str(original_job_root_dir / "results")))
    original_results_path = original_results_root_dir / job_id

    # working_dir: CLI arg takes precedence over data.json
    working_dir_base = args.working_dir or (Path(data["working_dir"]) if "working_dir" in data else None)

    # Create a unique temp directory inside working_dir_base so parallel runs don't collide.
    # This is the directory that gets deleted at the end.
    if working_dir_base is not None:
        working_dir_base.mkdir(parents=True, exist_ok=True)
        working_dir = Path(tempfile.mkdtemp(prefix=f"suite3dbatch_{job_id}_", dir=working_dir_base))
    else:
        working_dir = None

    tifs = collect_tifs(data)
    original_tifs = tifs
    print("Input files:")
    for t in tifs:
        print(f"  {t}")

    # Within the session temp directory, mirror the last path component of each root dir
    if working_dir is not None:
        job_root_dir = working_dir / original_job_root_dir.name
        results_root_dir = working_dir / original_results_root_dir.name
    else:
        job_root_dir = original_job_root_dir
        results_root_dir = original_results_root_dir

    results_path = results_root_dir / job_id
    # Create results dir early so we can start logging there
    results_path.mkdir(parents=True, exist_ok=True)

    log_path = results_path / f"{job_id}.log"
    log_file = open(log_path, "w", buffering=1)  # line-buffered
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(original_stdout, log_file)
    sys.stderr = TeeStream(original_stderr, log_file)

    tmp_dir = None
    try:
        if working_dir is not None:
            print(f"\nSession temp directory: {working_dir}")
            print("Copying input files to working directory...")
            tifs = copy_tifs_to_working_dir(tifs, working_dir / "input_tifs")
            print("Done copying.")

        chunk_size = int(data.get("tiff_trim_size", 0))
        if chunk_size:
            if working_dir is not None:
                # Split inside the working directory; cleaned up with it at the end
                tmp_dir = working_dir / "split_tifs"
                tmp_dir.mkdir(parents=True, exist_ok=True)
            else:
                tmp_parent = Path(data["temp_dir"]) if "temp_dir" in data else None
                if tmp_parent is not None:
                    tmp_parent.mkdir(parents=True, exist_ok=True)
                tmp_dir = Path(tempfile.mkdtemp(prefix="suite3dbatch_", dir=tmp_parent))
            print(f"\nSplitting TIFFs into chunks of {chunk_size} frames -> {tmp_dir}")
            block_size = int(data.get("block_size", 3))
            add_offset = bool(data.get("add_offset", False))
            tifs = split_tifs(tifs, chunk_size, tmp_dir, block_size=block_size, add_offset=add_offset)
            print("Split files:")
            for t in tifs:
                print(f"  {t}")

        # Save reproducibility files
        saved_params = params_to_json_serializable(params)
        with open(results_path / "params_used.json", "w") as f:
            json.dump(saved_params, f, indent=2)

        saved_data = dict(data)
        saved_data["data"] = [str(t) for t in original_tifs]
        saved_data.pop("root_path", None)  # paths are now absolute
        saved_data["results_root_dir"] = str(original_results_root_dir)
        saved_data["job_root_dir"] = str(original_job_root_dir)
        with open(results_path / "data_used.json", "w") as f:
            json.dump(saved_data, f, indent=2)

        # Run pipeline
        job = Job(job_root_dir, job_id, tifs=tifs,
                  params=params, create=True, overwrite=True, verbosity=3)
        job.params.update(params)

        job.run_init_pass()
        job.register()
        job.calculate_corr_map()
        job.segment_rois()
        job.compute_npil_masks()
        job.extract_and_deconvolve()

        job.export_results(results_path, result_dir_name="rois")

    finally:
        # Restore streams and flush log before copying it back
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.flush()
        log_file.close()

        # Clean up a standalone temp dir (only when not using working_dir)
        if tmp_dir is not None and tmp_dir.exists() and working_dir is None:
            shutil.rmtree(tmp_dir)
            print(f"\nCleaned up temporary directory: {tmp_dir}")

        if working_dir is not None and working_dir.exists():
            # Copy results directory back
            print(f"\nCopying results back to {original_results_path} ...")
            if original_results_path.exists():
                shutil.rmtree(original_results_path)
            original_results_root_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(results_path), str(original_results_path))

            # Copy job directory back
            full_job_id = "s3d-" + job_id
            working_job_path = job_root_dir / full_job_id
            original_job_path = original_job_root_dir / full_job_id
            if working_job_path.exists():
                print(f"Copying job directory back to {original_job_path} ...")
                if original_job_path.exists():
                    shutil.rmtree(original_job_path)
                original_job_root_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(working_job_path), str(original_job_path))

            # Clean up session temp directory (input copies, split tifs, working outputs)
            print(f"Cleaning up session temp directory: {working_dir} ...")
            shutil.rmtree(working_dir)
            print("Done.")


if __name__ == "__main__":
    main()
