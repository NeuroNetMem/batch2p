# batch2p

Batch 2-photon preprocessing script. Runs a configurable source extraction pipeline
from a single JSON configuration file. Optionally runs behavioral synchronization
(via `totalsync_2p`) after the imaging pipeline when `behavior_data` is present in
the configuration. The source extraction algorithm is selected via the
`source_extraction` field; currently supported: `suite3d`, `suite2p`.

## Installation

```bash
pip install -e .
```

This registers the `batch2p` command. Alternatively the script can be run
directly without installation:

```bash
python scripts/batch2p_run.py data_suite2p.json
```

## Usage

```
batch2p <data.json> [--working-dir DIR]
```

| Argument | Description |
|---|---|
| `data.json` | Path to the data/run configuration JSON file (required). |
| `--working-dir DIR` | Local scratch directory for intermediate files (optional). See [Working directory](#working-directory). |

## data.json fields

### Generic fields (all algorithms)

| Field | Required | Description |
|---|---|---|
| `source_extraction` | no | Source extraction algorithm to use. Default: `"suite3d"`. Supported: `"suite3d"`, `"suite2p"`. |
| `job_id` | yes | Unique string identifier for this run. Used as directory name for job and results output. |
| `job_root_dir` | yes | Directory in which the algorithm's job folder is created (Suite3D only; Suite2P writes results directly into `results_root_dir`). |
| `data` | yes | List of input TIFF files. Entries are relative to `root_path` if set. See [Input files](#input-files). |
| `root_path` | no | Base path prepended to all relative entries in `data`, `params_file`, and `pinsheet_file`. |
| `results_root_dir` | no | Directory under which the results folder (`<job_id>/`) is created. Defaults to `<job_root_dir>/results`. |
| `working_dir` | no | Same as `--working-dir`; the CLI flag takes precedence if both are provided. |
| `block_size` | no | Number of planes per volume (default `3`). Used for TIFF splitting and synced-output frame-index normalization. |
| `behavior_data` | no | List of `.b64` TotalSync telemetry files, one per entry in `data` (same order). When present, behavioral synchronization is run after the imaging pipeline. Requires `pinsheet_file`. |
| `pinsheet_file` | no (yes if `behavior_data` set) | Path to the TotalSync pin mapping JSON file. Relative paths are resolved against `root_path`. |
| `fill_tsync_gaps` | no | If `true`, interpolate timestamp gaps in the behavioral log rather than discarding frames after the first gap (default `false`). |

### Suite3D-specific fields

| Field | Required | Description |
|---|---|---|
| `params_file` | yes | Path to the Suite3D parameters JSON file. Relative paths are resolved against `root_path`. |
| `tiff_trim_size` | no | If `> 0`, split each input TIFF into chunks of this many frames before running Suite3D. |
| `add_offset` | no | Boolean passed to `split_3d_tiff_into_chunks` (default `false`). Only relevant when `tiff_trim_size > 0`. |
| `temp_dir` | no | Parent directory for the TIFF-split temp folder when no `working_dir` is set. Defaults to the system temp directory. |

### Suite2P-specific fields

| Field | Required | Description |
|---|---|---|
| `params_file` | yes | Path to the Suite2P parameters JSON file. Relative paths are resolved against `root_path`. |
| `temp_dir` | no | Parent directory for the Suite2P fast-disk scratch folder. Overridden by `--working-dir` if provided. Defaults to the system temp directory. |

> **Note:** `tiff_trim_size` is ignored by Suite2P. Suite2P processes all input TIFFs
> in one pass without chunking; set `tiff_trim_size` to `0` (or omit it) when using
> `"source_extraction": "suite2p"`.

### Input files

Each entry in `data` is resolved relative to `root_path` (if present) and may be:

- A `.tif` / `.tiff` file – added to the list directly.
- A directory – all `.tif` / `.tiff` files inside are added in lexicographic order.

### Example `data.json` for Suite2P

```json
{
  "source_extraction": "suite2p",
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "/home/user/src/ofl_2p_analysis/docs/params_default_suite2p.json",
  "data": [
    "00001/477116_20251118_00001.tif"
  ],
  "job_root_dir": "/data/ofl_2p/20251118",
  "job_id": "00001",
  "results_root_dir": "/data/ofl_2p/20251118/preprocessing_results",
  "tiff_trim_size": 0,
  "block_size": 3,
  "temp_dir": "/data/temp/scratch"
}
```

With behavioral synchronization:

```json
{
  "source_extraction": "suite2p",
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "/home/user/src/ofl_2p_analysis/docs/params_default_suite2p.json",
  "data": [
    "00001/477116_20251118_00001.tif"
  ],
  "behavior_data": [
    "20251118-152602_925.b64"
  ],
  "pinsheet_file": "/home/user/src/ofl_2p_analysis/docs/pinSheet_2026.json",
  "job_root_dir": "/data/ofl_2p/20251118",
  "job_id": "00001",
  "results_root_dir": "/data/ofl_2p/20251118/preprocessing_results",
  "tiff_trim_size": 0,
  "block_size": 3,
  "fill_tsync_gaps": true,
  "temp_dir": "/data/temp/scratch"
}
```

### Example `data.json` for Suite3D

```json
{
  "source_extraction": "suite3d",
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "params_default_suite3d.json",
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
  "source_extraction": "suite3d",
  "root_path": "/data/ofl_2p/20251118",
  "params_file": "params_default_suite3d.json",
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
  "fill_tsync_gaps": true,
  "temp_dir": "/data/temp"
}
```

## Suite2P pipeline details

Suite2P is invoked via `suite2p.run_s2p(db, settings)` where:

- **`settings`** is built by loading the `params_file` JSON and merging it into the
  Suite2P default settings dictionary (`suite2p.parameters.default_settings()`).
  The merge respects the two-level nested structure of Suite2P settings: top-level
  non-dict keys are overwritten directly; top-level dict keys (e.g. `"registration"`,
  `"detection"`) are merged at the second level. `torch_device` is auto-detected
  (`"cuda"` if a compatible GPU is available, otherwise `"cpu"`) unless explicitly
  set in the params file.

- **`db`** is constructed from both the data JSON and the params file:
  - `data_path` — a temporary `collected_input/` folder created inside the results
    directory containing copies of all input TIFFs (deleted after the run).
  - `fast_disk` — a unique temporary directory used by Suite2P for binary caching
    (deleted after the run). Parent is `temp_dir` from `data.json`, or the
    `--working-dir` path if provided.
  - `save_folder` — the results directory (`results_root_dir/<job_id>/`).
  - Acquisition parameters (`fs`, `tau`, `nplanes`, `nchannels`, etc.) are mirrored
    from `settings` into `db`.

Suite2P writes its output under `save_folder/`:

```
<results_root_dir>/<job_id>/
  combined/       F.npy  Fneu.npy  spks.npy  stat.npy  iscell.npy  …
  plane0/         F.npy  Fneu.npy  spks.npy  …
  plane1/         …
  plane2/         …
  params_used.json
  data_used.json
  <job_id>.log
```

## Working directory

When `--working-dir DIR` (or `working_dir` in `data.json`) is provided, the script
isolates all intermediate work in a uniquely-named temporary subdirectory inside
`DIR` (e.g. `DIR/batch2p_<job_id>_<random>/`). This allows multiple instances
to run in parallel against the same scratch mount.

Steps performed when a working directory is used:

1. Input TIFF files are copied to `<session_tmp>/input_tifs/`.
2. If `behavior_data` is present, `.b64` files are copied to `<session_tmp>/input_b64s/`.
3. For Suite3D, if TIFF splitting is requested it runs inside `<session_tmp>/split_tifs/`.
4. The extraction job and results are written inside `<session_tmp>`.
   For Suite2P, the fast-disk scratch directory is also created inside `<session_tmp>`.
5. On completion (or on error), the results folder is copied back to `results_root_dir/<job_id>/`
   and the job folder (Suite3D only) is copied back to `job_root_dir/`.
6. If behavioral synchronization ran, `behavior_sync/` is copied back to `results_root_dir/behavior_sync/`.
7. The session temp directory (including all input copies and `.b64` files) is deleted.

## Behavioral synchronization

When `behavior_data` is present in `data.json`, the script runs `totalsync_2p.synchronize()`
for each (tif, b64) pair after the extraction pipeline completes. The `.b64` files must be
listed in the same order as `data`, one file per tif entry. Synchronization depends only on
the original TIF file and the `.b64` file and is not algorithm-specific.

Outputs are written to `results_root_dir/behavior_sync/` and include, per session:

| File | Contents |
|---|---|
| `<session>_barcode_data.npz` | Raw decoded TotalSync telemetry arrays. |
| `<session>_frames_time_idx.npz` | Pynapple `Tsd` mapping scanner time (s) → tif frame index. |
| `<session>_behavior_sync_stats.pkl` | Synchronization statistics (barcode shift, match table, gap info). |

After synchronization, algorithm-specific synced outputs are created from the
extraction results, selecting `F`, `Fneu`, and `spks` traces at the synchronized
frame indices and saving them as pynapple `TsdFrame` objects.

### Suite3D synced outputs

Saved in `behavior_sync/`:

| File | Contents |
|---|---|
| `F_sync.npz` | Fluorescence traces at synchronized frames. |
| `Fneu_sync.npz` | Neuropil traces at synchronized frames. |
| `spks_sync.npz` | Deconvolved spike estimates at synchronized frames. |

### Suite2P synced outputs

Suite2P produces both combined (all-plane) and per-plane outputs. Synced versions
are created for all of them:

| File | Contents |
|---|---|
| `behavior_sync/F_sync.npz` | Combined fluorescence traces at synchronized frames. |
| `behavior_sync/Fneu_sync.npz` | Combined neuropil traces at synchronized frames. |
| `behavior_sync/spks_sync.npz` | Combined deconvolved spike estimates at synchronized frames. |
| `behavior_sync/plane0/F_sync.npz` | Plane-0 fluorescence traces at synchronized frames. |
| `behavior_sync/plane0/Fneu_sync.npz` | Plane-0 neuropil traces. |
| `behavior_sync/plane0/spks_sync.npz` | Plane-0 spike estimates. |
| `behavior_sync/plane1/…` | Same for plane 1. |
| `behavior_sync/plane2/…` | Same for plane 2. |

Frame indices from the behavioral sync (page-level indices in the raw TIFF) are
divided by `block_size` to convert them to volume-level indices before selecting
columns from the Suite2P arrays.

### Alignment strategy

- **With barcode** – a cross-correlogram between the tif aux trigger and the `Barcode (Scanner)` channel is used to find the time shift, then tif frames are matched one-to-one to scanner frame-clock pulses within a 25 ms tolerance.
- **Without barcode** – the first scanner frame-clock pulse is assumed to correspond to the first tif frame. If timestamp gaps are present in the behavioral log, alignment is restricted to the period before the first gap (or gaps are interpolated if `fill_tsync_gaps` is `true`).

## Adding a new source extraction algorithm

1. Create `batch2p/extractors/<name>.py` implementing a subclass of `SourceExtractor`
   from `batch2p.extractors.base`. The subclass must implement `run()`,
   `get_job_subdir()`, and `create_synced_outputs()`.
2. Register it in `batch2p/extractors/__init__.py` by adding an entry to `_EXTRACTORS`.
3. Set `"source_extraction": "<name>"` in `data.json`.

## Logging

All stdout and stderr are tee'd to `<results_path>/<job_id>.log` so that the full
run log is available alongside the results even when the script is run non-interactively.

## Reproducibility

Before launching the pipeline the script writes two files into the results directory:

- `data_used.json` – the run configuration with all file paths made absolute.
- `params_used.json` – the full settings dictionary actually passed to the algorithm
  (Suite2P: merged two-level dict; Suite3D: params JSON with numpy arrays serialized).
- `params_supplied.json` *(Suite2P only)* – the parameters as read from the user-supplied
  `params_file`, before merging with Suite2P defaults. Useful for comparing what was
  explicitly set versus what was inherited from defaults.
