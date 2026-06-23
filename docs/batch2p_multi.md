# batch2p-multi

Utility for generating one `data.json` file per session directory from a single
template. Designed for batch experiments where multiple directories share the
same pipeline configuration but differ only in their input files and paths.

## Installation

```bash
pip install -e .
```

This registers the `batch2p-multi` command.

## Usage

```
batch2p-multi <template_data.json> <dir_list.txt> --params-file <params.json>
              [--output-dir DIR] [--tif-regexp REGEXP] [--force-sync]
```

| Argument | Required | Description |
|---|---|---|
| `template_data.json` | yes | Template `data.json` (see [Template](#template)). |
| `dir_list.txt` | yes | Text file listing session directories, one per line. |
| `--params-file` | yes | Path to the `params.json` file. The same file is referenced in every generated `data.json`. |
| `--output-dir DIR` | no | Directory where generated `data.json` files are written. Default: current directory. |
| `--tif-regexp REGEXP` | no | Only include `.tif`/`.tiff` files whose filename matches this Python regular expression. |
| `--force-sync` | no | Require `.b64` files to be present in each directory and match the number of TIF files; skip directories that do not satisfy this condition. |

## Directory list file

A plain text file with one absolute directory path per line. Blank lines and
lines beginning with `#` are ignored. Paths that do not exist as directories
on the filesystem produce a warning and are skipped.

```
# Mouse 488503 Pichu
/vol/data/AATC/488503_Pichu/20260408_day1
/vol/data/AATC/488503_Pichu/20260409_day2
/vol/data/AATC/488503_Pichu/20260410_day3

# Mouse 488505 Cleffa
/vol/data/AATC/488505_Cleffa/20260412_day1
/vol/data/AATC/488505_Cleffa/20260413_day2
```

## Template

The template is a `data.json` file used as the base for every generated output.
Two substitution mechanisms are supported:

### Literal path substitution (recommended for real data.json files)

If the template has a `root_path` field, its value is treated as the
**prototype root**: every occurrence of that string in any field of the template
is replaced with the current directory. This means an existing `data.json` from
a single session can be used directly as a template without any manual editing —
fields like `job_root_dir` and `results_root_dir` are updated automatically.

Example template (`session1_data.json`):

```json
{
  "source_extraction": "suite2p",
  "root_path": "/vol/data/AATC/488503_Pichu/20260408_day1",
  "job_id": "AATC_r1",
  "job_root_dir": "/vol/data/AATC/488503_Pichu/20260408_day1/AATC_r1",
  "results_root_dir": "/vol/data/AATC/488503_Pichu/20260408_day1/AATC_r1_results",
  ...
}
```

For directory `/vol/data/AATC/488503_Pichu/20260409_day2`, the generated output will have:
- `root_path` → `/vol/data/AATC/488503_Pichu/20260409_day2`
- `job_root_dir` → `/vol/data/AATC/488503_Pichu/20260409_day2/AATC_r1`
- `results_root_dir` → `/vol/data/AATC/488503_Pichu/20260409_day2/AATC_r1_results`

### Placeholder substitution

String fields may also contain `{{ variable }}` placeholders:

| Placeholder | Replaced with |
|---|---|
| `{{ root_dir }}` | Absolute path of the current directory. |
| `{{ job_id }}` | The resolved `job_id` for this directory (after `root_dir` substitution). |

Placeholders whose variable is absent or empty are left verbatim.

Both mechanisms can be combined: literal path replacement runs first, then
`{{ }}` placeholder substitution.

## File collection

For each directory the script collects:

- **TIF files** — all `.tif` and `.tiff` files in the directory, sorted
  lexicographically. If `--tif-regexp` is given, only files whose name matches
  the pattern are included.
- **`.b64` files** — all `.b64` files in the directory, sorted lexicographically.

Directories with no TIF files (after regexp filtering) are skipped with a
warning.

With `--force-sync`, directories that have no `.b64` files, or where the count
of `.b64` files does not match the count of TIF files, are also skipped with a
warning.

## Output

For each directory a file named `<job_id>_<N>_data.json` is written to
`--output-dir`, where `<N>` is the 1-based index zero-padded to the width
needed for the total number of directories.

The following fields are always set (overriding any template value):

| Field | Value |
|---|---|
| `job_id` | Template `job_id` (after path and placeholder substitution) with `_<N>` appended. |
| `params_file` | Absolute path from `--params-file`. |
| `root_path` | Absolute path of the current directory. |
| `data` | List of absolute TIF file paths collected from the directory. |
| `behavior_data` | List of absolute `.b64` file paths (set only if `.b64` files were found; removed from output if the template had it but the directory has none). |

All other fields are inherited from the template after path/placeholder
substitution.

## Example

```bash
batch2p-multi session1_data.json dirs.txt \
    --params-file /data/params/AATC_r1_params.json \
    --output-dir /data/json_outputs \
    --force-sync
```

Output:

```
  [ 1/32] AATC_r1_01_data.json  (1 tif, 1 b64)  /vol/data/AATC/488503_Pichu/20260408_day1
  [ 2/32] AATC_r1_02_data.json  (1 tif, 1 b64)  /vol/data/AATC/488503_Pichu/20260409_day2
  ...

Generated 32 data.json file(s) in: /data/json_outputs
```

Each generated file can then be run with:

```bash
batch2p /data/json_outputs/AATC_r1_01_data.json --working-dir /data/scratch
```

Or submitted as a SLURM array job using the `batch2p-gui` SLURM script
generator or a custom Jinja2 template.
