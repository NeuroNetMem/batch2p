# suite3dbatch

Batch Suite3D preprocessing script. Runs the full Suite3D pipeline (init pass →
registration → correlation map → ROI segmentation → neuropil masks → extraction /
deconvolution → export) from a single JSON configuration file. Optionally runs
behavioral synchronization (via `totalsync_2p`) after the imaging pipeline when
`behavior_data` is present in the configuration.

## Installation

```bash
pip install -e .
```

This registers the `suite3dbatch` command. Alternatively the script can be run
directly without installation:

```bash
python scripts/suite3dbatch.py data.json
```

## Usage

```
suite3dbatch <data.json> [--working-dir DIR]
```

| Argument | Description |
|---|---|
| `data.json` | Path to the data/run configuration JSON file (required). |
| `--working-dir DIR` | Local scratch directory for intermediate files (optional). See [Working directory](#working-directory). |

## data.json fields

| Field | Required | Description                                                                                                                                                                        |
|---|---|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `params_file` | yes | Path to the Suite3D parameters JSON file. Relative paths are resolved against `root_path`.                                                                                         |
| `job_id` | yes | Unique string identifier for this run. Used as directory name for job and results output.                                                                                          |
| `job_root_dir` | yes | Directory in which the Suite3D job folder (`s3d-<job_id>/`) is created.                                                                                                            |
| `data` | yes | List of input items (TIFF files or directories). See [Input files](#input-files).                                                                                                  |
| `root_path` | no | Base path prepended to all relative entries in `data` and to a relative `params_file`.                                                                                             |
| `results_root_dir` | no | Directory under which the results folder (`<job_id>/`) is created. Defaults to `<job_root_dir>/results`.                                                                           |
| `working_dir` | no | Same as `--working-dir`; the CLI flag takes precedence if both are provided.                                                                                                       |
| `tiff_trim_size` | no | If `> 0`, split each input TIFF into chunks of this many frames before processing.                                                                                                 |
| `block_size` | no | Block size passed to `split_3d_tiff_into_chunks` (default `3`). For volumetric imaging.                                                                                            |
| `add_offset` | no | Boolean passed to `split_3d_tiff_into_chunks` (default `false`). Only used when `tiff_trim_size > 0`.                                                                              |
| `temp_dir` | no | Parent directory for the TIFF-split temp folder when no `working_dir` is set. Defaults to the system temp directory.                                                               |
| `behavior_data` | no | List of `.b64` TotalSync telemetry files, one per entry in `data` (same order). When present, behavioral synchronization is run after the imaging pipeline. Requires `pinsheet_file`. |
| `pinsheet_file` | no (yes if `behavior_data` set) | Path to the TotalSync pin mapping JSON file. Relative paths are resolved against `root_path`.                                                                                      |

### Input files

Each entry in `data` is resolved relative to `root_path` (if present) and may be:

- A `.tif` / `.tiff` file – added to the list directly.
- A directory – all `.tif` / `.tiff` files inside are added in lexicographic order.

### Example `data.json`

```json
{
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "params_default.json",
  "data": [
    "00001/477116_20251118_00001.tif"
  ],
  "job_root_dir": "/data/ofl_2p/20251118",
  "job_id": "00001split",
  "results_root_dir": "/data/ofl_2p/20251118/results",
  "tiff_trim_size": 9999,
  "block_size": 3,
  "add_offset": false,
  "temp_dir": "/data/temp"
}
```

With behavioral synchronization:

```json
{
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "params_default.json",
  "data": [
    "00001/477116_20251118_00001.tif"
  ],
  "behavior_data": [
    "20251118_171019_550.b64"
  ],
  "pinsheet_file": "/home/user/src/ofl_2p_analysis/docs/pinSheet_2026.json",
  "job_root_dir": "/data/ofl_2p/20251118",
  "job_id": "00001split",
  "results_root_dir": "/data/ofl_2p/20251118/results",
  "tiff_trim_size": 9999,
  "block_size": 3,
  "add_offset": false,
  "temp_dir": "/data/temp"
}
```

## Working directory

When `--working-dir DIR` (or `working_dir` in `data.json`) is provided, the script
isolates all intermediate work in a uniquely-named temporary subdirectory inside
`DIR` (e.g. `DIR/suite3dbatch_<job_id>_<random>/`). This allows multiple instances
to run in parallel against the same scratch mount.

Steps performed when a working directory is used:

1. Input TIFF files are copied to `<session_tmp>/input_tifs/`.
2. If `behavior_data` is present, `.b64` files are copied to `<session_tmp>/input_b64s/`.
3. If TIFF splitting is requested it runs inside `<session_tmp>/split_tifs/`.
4. The Suite3D job and results are written inside `<session_tmp>`.
5. On completion (or on error), the results folder is copied back to `results_root_dir/<job_id>/`
   and the job folder (`s3d-<job_id>/`) is copied back to `job_root_dir/`.
6. If behavioral synchronization ran, `behavior_sync/` is copied back to `results_root_dir/behavior_sync/`.
7. The session temp directory (including all input copies and `.b64` files) is deleted.

## Behavioral synchronization

When `behavior_data` is present in `data.json`, the script runs `totalsync_2p.synchronize()`
for each (tif, b64) pair after the Suite3D pipeline completes. The `.b64` files must be
listed in the same order as `data`, one file per tif entry.

Outputs are written to `results_root_dir/behavior_sync/` and include, per session:

| File | Contents |
|---|---|
| `<session>_barcode_data.npz` | Raw decoded TotalSync telemetry arrays. |
| `<session>_frames_time_idx.npz` | Pynapple `Tsd` mapping scanner time (s) → tif frame index. |
| `<session>_behavior_sync_stats.pkl` | Synchronization statistics (barcode shift, match table, gap info). |

Alignment strategy:

- **With barcode** – a cross-correlogram between the tif aux trigger and the `Barcode (Scanner)` channel is used to find the time shift, then tif frames are matched one-to-one to scanner frame-clock pulses within a 25 ms tolerance.
- **Without barcode** – the first scanner frame-clock pulse is assumed to correspond to the first tif frame. If timestamp gaps are present in the behavioral log, alignment is restricted to the period before the first gap.

## Logging

All stdout and stderr are tee'd to `<results_path>/<job_id>.log` so that the full
run log is available alongside the results even when the script is run non-interactively.

## Reproducibility

Before launching the pipeline the script writes two files into the results directory:

- `params_used.json` – the Suite3D parameters actually used.
- `data_used.json` – the run configuration with all file paths made absolute.
