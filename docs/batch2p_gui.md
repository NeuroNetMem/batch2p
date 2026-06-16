# batch2p GUI

Visual configurator for `batch2p` run configurations. Produces the
`data_*.json` and `params_*.json` files consumed by the `batch2p` CLI without
requiring manual JSON editing. Supports parameter sweeps that generate a full
grid of run configurations in one step.

## Launch

```bash
batch2p-gui          # after pip install -e .
python -m batch2p.gui
```

Requires PyQt5 (`pip install pyqt5`).

## Window layout

The window is divided into two resizable panels.

```
┌──────────────────────────┬────────────────────────────────────────────────┐
│  Input Files             │  Run Configuration  │  Algorithm Parameters   │
│  ─────────────────────── │  (tab)              │  (tab)                  │
│  Root Path               │                     │                         │
│  ┌──────────┬──────────┐ │  Algorithm          │  [Load defaults]        │
│  │ TIFFs    │ .b64s    │ │  Job settings       │  [Load from JSON…]      │
│  │ (list)   │ (list)   │ │  Directories        │  [Reset selected]       │
│  └──────────┴──────────┘ │  Sync settings      │                         │
│  [Load list] [Save list] │  Output dir         │  Section│Param│Value│Sw │
└──────────────────────────┴─────────────────────┴─────────────────────────┘
```

---

## Left panel — Input Files

### Root Path

The `root_path` written into every generated `data.json`. It is the base
directory used to express TIFF and `.b64` paths as relative entries. Set this
to the path as it will appear **on the processing server**, which may differ
from the path used when selecting files on the local machine.

### TIFF files / .b64 files

Two side-by-side lists. Row *i* of the TIFF list corresponds to row *i* of the
`.b64` list — selecting a row in either list highlights the matching row in the
other.

| Button | Action |
|--------|--------|
| **Add…** | Open a file-selection dialog and append files to the list. |
| **Remove** | Remove the currently selected files. |
| **▲ / ▼** | Move the selected file up or down in the list. |

`.b64` files are optional. When present the number of `.b64` files must equal
the number of TIFF files; a warning is shown otherwise.

### Save / Load file list

The file list (root path + TIFF paths + `.b64` paths) can be saved to a JSON
snapshot and reloaded in a later session. This is independent of the full
project save/load described below.

---

## Right panel — Run Configuration tab

### Algorithm

Select **Suite2P** or **Suite3D**. The choice controls:
- which fields are shown in this tab (Suite3D-only fields `tiff_trim_size` and
  `add_offset` are hidden for Suite2P),
- which parameter table is active in the Algorithm Parameters tab,
- the `source_extraction` value written into `data.json`.

### Output Directory for Generated JSON Files

The directory where `data_*.json` and `params_*.json` will be written. This is
separate from the data directories and from `results_root_dir`.

### Run-configuration fields

These correspond to the fields of `data.json` documented in
[batch2p.md](batch2p.md).

| Field | Algorithm | Description |
|-------|-----------|-------------|
| Job ID | both | Unique run identifier; used as the output subdirectory name. |
| Job Root Dir | both | Directory where Suite3D creates its job folder (not used by Suite2P). |
| Results Root Dir | both | Parent of the `<job_id>` results folder. |
| Temp / Scratch Dir | both | Parent for the Suite2P fast-disk scratch dir or Suite3D TIFF-split temp dir. |
| Working Dir | both | Isolate all processing in a temp subdirectory here and copy results back on completion. |
| Block Size (planes/vol) | both | Planes per imaging volume; used for frame-index normalisation during behavioural sync. |
| Fill TSync Gaps | both | Interpolate gaps in the behavioural log instead of truncating. |
| Ignore Barcode | both | Skip barcode-based alignment and fall back to frame-clock onset matching. |
| Pinsheet File | both | Path to the TotalSync pin-mapping JSON (required when `.b64` files are provided). A **…** browse button opens a file picker. |
| TIFF Trim Size | Suite3D | Split each TIFF into chunks of this many frames before processing. Set `0` to disable. |
| Add Offset | Suite3D | Pass `add_offset=True` to `split_3d_tiff_into_chunks`. |

---

## Right panel — Algorithm Parameters tab

### Loading parameters

| Button | Action |
|--------|--------|
| **Load built-in defaults** | Restore all parameter values to the built-in defaults (Suite2P or Suite3D). |
| **Load from JSON file…** | Read a `params_*.json` file and update any matching parameters in the table. Parameters not found in the file are left unchanged. |
| **Reset selected to default** | Restore the currently selected row's value to its built-in default. |

### Parameter table

Each row represents one algorithm parameter.

| Column | Description |
|--------|-------------|
| **Section** | Logical group (e.g. `registration`, `detection` for Suite2P; `Mandatory`, `Registration` for Suite3D). Section `—` indicates a top-level parameter. |
| **Parameter** | Parameter name as it will appear in the JSON file. |
| **Value** | Current value. Double-click (or press Enter) to edit. Accepts any Python literal or numpy expression (see below). |
| **Sweep** ☐ | When ticked, the value is treated as a list of values to sweep over (see [Parameter sweep](#parameter-sweep)). The cell turns blue. |

Clicking any row displays the full parameter description in the pane below the
table.

### Editing values

Values are entered as Python expressions:

| Type | Example |
|------|---------|
| Number | `1.15`, `300`, `0` |
| Boolean | `True`, `False` |
| String | `'maximin'` |
| List / tuple | `[128, 128]`, `(4, 200, 200)` |
| Numpy range | `np.arange(0, 30)`, `np.linspace(0.1, 1.0, 5)` |

---

## Parameter sweep

Any parameter can be swept over a set of values by ticking its **Sweep**
checkbox and entering a list expression in the Value column:

```
[0.1, 0.5, 1.0]         # three values
np.arange(0.5, 2.0, 0.5) # four values: 0.5, 1.0, 1.5
```

When multiple parameters are swept, the **Cartesian product** is generated. A
live counter at the top right of the tab shows the total number of
configurations:

```
Sweep: threshold_scaling: 3 × win_baseline: 4 = 12 configs
```

Each configuration produces one `params_*.json` / `data_*.json` pair. Files
are numbered with a zero-padded index:

```
<output_dir>/
  myjob_01_params.json   myjob_01_data.json
  myjob_02_params.json   myjob_02_data.json
  …
  myjob_12_params.json   myjob_12_data.json
```

If no parameters are swept, a single unnumbered pair is produced:

```
<output_dir>/
  myjob_params.json   myjob_data.json
```

Each `data_*.json` file contains an absolute `params_file` path pointing to its
corresponding `params_*.json` file.

An error dialog is shown if any sweep expression is syntactically invalid or
does not evaluate to a list.

---

## Comments field

A free-form **Comments** text box is available in the Algorithm Parameters tab.
Its value is written into the generated `params_*.json` under the key
`"comments"` and is ignored by `batch2p` and all extractors. It is saved and
restored by project save/load.

---

## SLURM script generation

A **SLURM Job Scripts** group box appears in the Run Configuration tab. When
enabled, the GUI renders a Jinja2 template into a `.sh` SLURM script alongside
the generated JSON files.

| Control | Description |
|---------|-------------|
| **Generate .sh scripts from Jinja2 template** checkbox | Enable/disable SLURM script generation. |
| Template path field | Path to the Jinja2 template file (`.sh.in`, `.j2`, etc.). |
| **Browse…** button | Open a file picker for the template. |

### Template variables

The following variables are available inside the template:

| Variable | Description |
|----------|-------------|
| `is_array` | `True` if more than one configuration is being generated (sweep mode). |
| `n_jobs` | Total number of configurations. |
| `index_digits` | Zero-padding width for the job index (e.g. `2` for `01`, `02`…). |
| `out_dir` | Absolute path to the output directory. |
| `job_id` | The Job ID string. |
| `data_file` | Absolute path to the single `data.json` (non-array case only). |
| `working_dir` | Value of the Working Dir field (empty string if not set). |

A reference template is provided at `docs/job1.sh.in`. For a sweep it emits a
SLURM array job (`--array=1-N`); for a single configuration it emits a plain
job.

Requires `jinja2` (`pip install jinja2`). If the package is missing or the
template cannot be loaded, an error dialog is shown before any files are
written.

---

## Generate JSON files

Click **⚙ Generate JSON files** in the toolbar (or use `File > Generate JSON
files…`, shortcut `Ctrl+G`).

Before writing, the GUI validates:
- Output directory is set.
- At least one TIFF file is selected.
- Job ID is not empty.
- All sweep expressions are valid Python/numpy and evaluate to non-empty lists.

A confirmation dialog summarises the algorithm, job ID, output directory, and
number of configurations to be produced. After confirmation, files are written
and a summary of generated filenames is shown.

---

## Project save / load

`File > Save project…` / `File > Open project…` (`.b2p.json`) persist the
complete GUI state: file lists, root path, run-configuration fields, and the
full parameter table (values and sweep flags) for both Suite2P and Suite3D
simultaneously. This allows switching between algorithms and resuming work
across sessions without re-entering settings.

The file list can also be saved and loaded independently via the **Save file
list** / **Load file list** buttons in the Input Files panel.
