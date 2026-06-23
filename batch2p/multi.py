#!/usr/bin/env python3
"""batch2p-multi — generate one data.json per directory from a template.

Usage:
    batch2p-multi <template_data.json> <dir_list.txt> --params-file <params.json> [--output-dir <dir>]

The template data.json may contain {{ job_id }} and {{ root_dir }} placeholders,
which are substituted per-directory at generation time.  The dir_list file must
contain one directory path per line (blank lines and lines starting with # are
ignored).

For each directory the script:
  - collects all .tif/.tiff files and .b64 files (lexicographically sorted),
  - substitutes {{ job_id }} and {{ root_dir }} in all string fields,
  - writes <output_dir>/<job_id>_<n>_data.json  (1-based index, zero-padded).
"""
import argparse
import json
import re
import sys
from pathlib import Path


def _apply_template_vars(obj, variables: dict):
    """Recursively replace {{ var }} placeholders in string values.

    Placeholders whose variable is absent or empty are left verbatim.
    """
    if isinstance(obj, str):
        def _replace(m):
            val = variables.get(m.group(1).strip())
            return val if val else m.group(0)
        return re.sub(r'\{\{\s*(\w+)\s*\}\}', _replace, obj)
    if isinstance(obj, dict):
        return {k: _apply_template_vars(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_template_vars(x, variables) for x in obj]
    return obj


def _replace_literal(obj, old: str, new: str):
    """Recursively replace all occurrences of `old` with `new` in string values."""
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, dict):
        return {k: _replace_literal(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_literal(x, old, new) for x in obj]
    return obj


def _collect_files(directory: Path, pattern: str) -> list[str]:
    return sorted(str(p) for p in directory.glob(pattern))


def main():
    parser = argparse.ArgumentParser(
        description="Generate one data.json per directory from a template."
    )
    parser.add_argument("template",       help="Template data.json with {{ }} placeholders.")
    parser.add_argument("dir_list",       help="Text file with one directory per line.")
    parser.add_argument("--params-file",  required=True,
                        help="Path to the params.json file (same for all outputs).")
    parser.add_argument("--output-dir",   default=".",
                        help="Directory where generated data.json files are written (default: cwd).")
    parser.add_argument("--tif-regexp",   default=None,
                        help="Only include .tif/.tiff files whose filename matches this regexp.")
    parser.add_argument("--force-sync",   action="store_true",
                        help="Require .b64 files to be present and match the number of tif files; "
                             "skip directories where this condition is not met.")
    args = parser.parse_args()

    template_path = Path(args.template)
    dir_list_path = Path(args.dir_list)
    params_file   = str(Path(args.params_file).resolve())
    out_dir       = Path(args.output_dir)

    tif_regexp = re.compile(args.tif_regexp) if args.tif_regexp else None

    # Load template
    if not template_path.exists():
        sys.exit(f"Template not found: {template_path}")
    with open(template_path) as f:
        template = json.load(f)

    # Load directory list
    if not dir_list_path.exists():
        sys.exit(f"Directory list not found: {dir_list_path}")
    directories = []
    with open(dir_list_path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if not p.is_dir():
                print(f"Warning: not a directory, skipping: {line}", file=sys.stderr)
                continue
            directories.append(p)

    if not directories:
        sys.exit("No valid directories found in the list.")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive base job_id from the template (may itself contain a placeholder)
    base_job_id = template.get("job_id", "run")
    digits = len(str(len(directories)))

    # If the template has a literal root_path, treat it as the prototype root: every
    # occurrence of that path in any string field will be replaced with the current
    # directory.  This lets real data.json files (with no {{ }} placeholders) be used
    # directly as templates without manual editing.
    proto_root = template.get("root_path", "").rstrip("/")

    generated = []
    for idx, directory in enumerate(directories, start=1):
        root_dir = str(directory.absolute())

        # Collect files
        tif_files = sorted(set(
            _collect_files(directory, "*.tif") +
            _collect_files(directory, "*.tiff")
        ))
        if tif_regexp is not None:
            tif_files = [p for p in tif_files if tif_regexp.search(Path(p).name)]
        if not tif_files:
            print(f"Warning: no tif files found, skipping: {directory}", file=sys.stderr)
            continue
        b64_files = _collect_files(directory, "*.b64")
        if args.force_sync:
            if not b64_files:
                print(f"Warning: --force-sync: no b64 files found, skipping: {directory}", file=sys.stderr)
                continue
            if len(b64_files) != len(tif_files):
                print(f"Warning: --force-sync: {len(b64_files)} b64 vs {len(tif_files)} tif, skipping: {directory}", file=sys.stderr)
                continue

        # Substitute variables in the template (produces the per-dir job_id).
        # Step 1: replace the prototype root_path literally in all string fields so
        #   that templates with real paths (no {{ }} placeholders) work correctly.
        # Step 2: apply {{ }} placeholder substitution for explicit placeholders.
        suffix = f"_{idx:0{digits}d}"
        working = _replace_literal(template, proto_root, root_dir) if proto_root else template
        resolved_base_job_id = _apply_template_vars(
            _replace_literal(base_job_id, proto_root, root_dir) if proto_root else base_job_id,
            {"root_dir": root_dir},
        )
        variables = {"job_id": resolved_base_job_id, "root_dir": root_dir}
        data_dict = _apply_template_vars(working, variables)

        # Resolve the job_id after substitution, then append numeric suffix
        resolved_job_id = data_dict.get("job_id", resolved_base_job_id)
        final_job_id = f"{resolved_job_id}{suffix}"

        data_dict["job_id"]      = final_job_id
        data_dict["params_file"] = params_file
        data_dict["root_path"]   = root_dir
        data_dict["data"]        = tif_files
        if b64_files:
            data_dict["behavior_data"] = b64_files
        elif "behavior_data" in data_dict:
            del data_dict["behavior_data"]

        out_path = out_dir / f"{final_job_id}_data.json"
        with open(out_path, "w") as f:
            json.dump(data_dict, f, indent=2)

        generated.append(out_path)
        print(f"  [{idx:>{digits}}/{len(directories)}] {out_path.name}  ({len(tif_files)} tif, {len(b64_files)} b64)  {root_dir}")

    print(f"\nGenerated {len(generated)} data.json file(s) in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
