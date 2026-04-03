#!/usr/bin/env python3
"""
Batch suite3d preprocessing script.

Usage:
    python suite3dbatch.py <params.json> <data.json>
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


def main():
    parser = argparse.ArgumentParser(description="Batch suite3d preprocessing")
    parser.add_argument("params_json", type=Path, help="Path to params JSON file")
    parser.add_argument("data_json", type=Path, help="Path to data JSON file")
    args = parser.parse_args()

    params = load_params(args.params_json)

    with open(args.data_json) as f:
        data = json.load(f)

    tifs = collect_tifs(data)
    original_tifs = tifs
    print("Input files:")
    for t in tifs:
        print(f"  {t}")

    job_root_dir = data["job_root_dir"]
    job_id = data["job_id"]
    results_root_dir = Path(data.get("results_root_dir", str(Path(job_root_dir) / "results")))
    results_path = results_root_dir / job_id

    tmp_dir = None
    try:
        chunk_size = int(data.get("tiff_trim_size", 0))
        if chunk_size:
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
        results_path.mkdir(parents=True, exist_ok=True)
        saved_params = params_to_json_serializable(params)
        with open(results_path / "params_used.json", "w") as f:
            json.dump(saved_params, f, indent=2)

        saved_data = dict(data)
        saved_data["data"] = [str(t) for t in original_tifs]
        saved_data.pop("root_path", None)  # paths are now absolute
        saved_data["results_root_dir"] = str(results_root_dir)
        saved_data["job_root_dir"] = str(job_root_dir)
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
        if tmp_dir is not None and tmp_dir.exists():
            shutil.rmtree(tmp_dir)
            print(f"\nCleaned up temporary directory: {tmp_dir}")


if __name__ == "__main__":
    main()
