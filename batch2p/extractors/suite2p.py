"""Suite2P source extraction algorithm."""
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np

from .base import SourceExtractor


def _update_two_level_dict(d1: dict, d2: dict) -> dict:
    """Update d1 with values from d2, respecting two-level dict structure.

    Non-dict fields in d1 are overwritten by the corresponding field in d2.
    Dict fields in d1 are updated at the second level with the corresponding
    second-level dict in d2 (if present).
    """
    for key, val in d2.items():
        if key in d1 and isinstance(d1[key], dict):
            if isinstance(val, dict):
                d1[key].update(val)
        else:
            d1[key] = val
    return d1


def _detect_torch_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    try:
        import cupy
        if cupy.cuda.runtime.getDeviceCount() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _load_settings(params_path: Path) -> tuple[dict, dict]:
    """Load suite2p settings, returning (user_params, merged_settings).

    user_params: the params as read from the JSON file (with torch_device added
        if not present), before merging with suite2p defaults.
    merged_settings: suite2p default_settings() updated with user_params.
    """
    from suite2p.parameters import default_settings

    with open(params_path) as f:
        user_params = json.load(f)

    if "torch_device" not in user_params:
        user_params["torch_device"] = _detect_torch_device()

    merged = _update_two_level_dict(default_settings(), user_params)
    return user_params, merged


def _params_to_json_serializable(params: dict) -> dict:
    result = {}
    for k, v in params.items():
        if isinstance(v, np.ndarray):
            result[k] = v.tolist()
        elif isinstance(v, dict):
            result[k] = _params_to_json_serializable(v)
        else:
            result[k] = v
    return result


def _get_tif_n_frames(tif_path: Path) -> int:
    import tifffile
    with tifffile.TiffFile(tif_path) as tif:
        return len(tif.pages)


def _build_sync_indices(
    tif_files: list[Path],
    sync_results: list[dict],
    block_size: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return a list of (global_vol_indices, t_frames) per tif file.

    global_vol_indices: volume-level indices into the suite2p combined array for
        this tif's contribution (i.e. local volume indices + cumulative offset).
    t_frames: timestamps corresponding to those indices, with cumulative time offset.
    """
    # Raw page counts are used for offsets; block_size converts pages → volumes.
    frame_offsets = [0]
    for tif in tif_files[:-1]:
        frame_offsets.append(frame_offsets[-1] + _get_tif_n_frames(tif))

    time_offsets = [0.0]
    for stats in sync_results:
        time_offsets.append(time_offsets[-1] + stats['frames_time_idx'].t[-1])

    result = []
    for stats, frame_offset, time_offset in zip(sync_results, frame_offsets, time_offsets):
        frames_time_idx = stats['frames_time_idx']
        local_indices = frames_time_idx.d.astype(int)

        if block_size > 1:
            local_indices = np.unique((local_indices / block_size).astype(int))
            t_frames = frames_time_idx.t[local_indices * block_size]
            vol_offset = frame_offset // block_size
        else:
            t_frames = frames_time_idx.t
            vol_offset = frame_offset

        result.append((local_indices + vol_offset, t_frames + time_offset))
    return result


def _sync_source_dir(
    source_dir: Path,
    out_dir: Path,
    sync_indices: list[tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Load F/Fneu/spks from source_dir and save synced TsdFrames to out_dir.

    Returns True if any arrays were found and processed.
    """
    import pynapple as nap

    arrays_to_sync = {}
    for name in ('F', 'Fneu', 'spks'):
        npy_path = source_dir / f"{name}.npy"
        if npy_path.exists():
            arrays_to_sync[name] = np.load(npy_path)

    if not arrays_to_sync:
        return False

    out_dir.mkdir(parents=True, exist_ok=True)

    # Accumulate selected columns across all tif files; timestamps are already
    # globally offset so we can concatenate directly.
    all_selected = {name: [] for name in arrays_to_sync}
    all_t = []
    for global_indices, t_frames in sync_indices:
        for name, arr in arrays_to_sync.items():
            valid_mask = global_indices < arr.shape[1]
            gi = global_indices[valid_mask]
            all_selected[name].append(arr[:, gi])
        # Use the shortest valid time vector across arrays for this segment
        n_valid = min(
            (global_indices < arr.shape[1]).sum() for arr in arrays_to_sync.values()
        )
        all_t.append(t_frames[:n_valid])

    t = np.concatenate(all_t)
    for name, chunks in all_selected.items():
        selected = np.concatenate(chunks, axis=1)  # (n_cells, total_frames)
        n = min(len(t), selected.shape[1])
        tsd_frame = nap.TsdFrame(t=t[:n], d=selected[:, :n].T, time_units='s')
        out_path = out_dir / f"{name}_sync.npz"
        tsd_frame.save(out_path)
        print(f"    Saved {out_path.relative_to(out_dir.parent)} ({tsd_frame.shape})")

    return True


def create_synced_outputs(
    tif_files: list[Path],
    sync_results: list[dict],
    suite2p_output_dir: Path,
    behavior_sync_dir: Path,
    block_size: int = 3,
) -> None:
    """Select suite2p traces by synced frame indices and save as pynapple TsdFrames.

    Processes the combined output directory and each per-plane directory found
    under suite2p_output_dir.  Synced files are saved as:
      behavior_sync_dir/F_sync.npz  (combined)
      behavior_sync_dir/plane0/F_sync.npz  (per plane)
      ...
    """
    sync_indices = _build_sync_indices(tif_files, sync_results, block_size)

    # Combined output
    combined_dir = suite2p_output_dir / "combined"
    if not _sync_source_dir(combined_dir, behavior_sync_dir, sync_indices):
        print("  No F/Fneu/spks arrays found in suite2p combined output, skipping.")

    # Per-plane outputs (plane0, plane1, ...)
    plane_dirs = sorted(suite2p_output_dir.glob("plane[0-9]*"))
    for plane_dir in plane_dirs:
        out_dir = behavior_sync_dir / plane_dir.name
        if not _sync_source_dir(plane_dir, out_dir, sync_indices):
            print(f"  No arrays found in {plane_dir.name}, skipping.")


class Suite2PExtractor(SourceExtractor):
    def __init__(self, data: dict):
        super().__init__(data)
        params_file = Path(data["params_file"])
        if not params_file.is_absolute():
            params_file = Path(data.get("root_path", ".")) / params_file
        self.user_params, self.settings = _load_settings(params_file)

    def get_job_subdir(self, job_id: str) -> str:
        # Suite2P writes all outputs directly into results_path, so there is no
        # separate job directory created under job_root_dir.  Returning a name
        # that will not be created keeps the CLI copy-back step a no-op.
        return f"s2p-{job_id}"

    def save_reproducibility_info(self, results_path: Path) -> None:
        with open(results_path / "params_supplied.json", "w") as f:
            json.dump(_params_to_json_serializable(self.user_params), f, indent=2)
        with open(results_path / "params_used.json", "w") as f:
            json.dump(_params_to_json_serializable(self.settings), f, indent=2)

    def run(self, tifs: list[Path], job_root_dir: Path, job_id: str, results_path: Path) -> None:
        import suite2p

        # Collect all tif files into a single flat folder as required by suite2p.
        # This folder is cleaned up after the run.
        collected_folder = results_path / "collected_input"
        collected_folder.mkdir(parents=True, exist_ok=True)
        for tif in tifs:
            dst = collected_folder / tif.name
            shutil.copy2(tif, dst)
            print(f"  Collected {tif.name} -> {dst}")

        # Create a unique scratch directory for suite2p's binary files.
        # Parent is taken from data["temp_dir"] (which the CLI may override with
        # --working-dir before calling run()).
        temp_dir_parent = self.data.get("temp_dir")
        if temp_dir_parent is not None:
            fast_disk_parent = Path(temp_dir_parent)
            fast_disk_parent.mkdir(parents=True, exist_ok=True)
        else:
            fast_disk_parent = None
        fast_disk = Path(tempfile.mkdtemp(prefix=f"s2p_{job_id}_", dir=fast_disk_parent))

        db = {
            "data_path": [str(collected_folder)],
            "fast_disk": str(fast_disk),
            "delete_bin": False,
            "move_bin": True,
            "save_folder": str(results_path),
        }
        # Mirror acquisition parameters from settings into db as the notebook does.
        for key in ('fs', 'tau', 'nplanes', 'nchannels', 'functional_chan',
                    'force_sktiff', 'ignore_flyback', 'keep_movie_raw'):
            if key in self.settings:
                db[key] = self.settings[key]

        try:
            suite2p.run_s2p(db, self.settings)
        finally:
            if collected_folder.exists():
                shutil.rmtree(collected_folder)
                print(f"  Cleaned up collected input folder: {collected_folder}")
            if fast_disk.exists():
                shutil.rmtree(fast_disk)
                print(f"  Cleaned up fast_disk scratch directory: {fast_disk}")

    def create_synced_outputs(
        self,
        tif_files: list[Path],
        sync_results: list[dict],
        results_path: Path,
        behavior_sync_dir: Path,
        block_size: int,
    ) -> None:
        # Suite2P saves combined outputs directly under results_path/combined/
        create_synced_outputs(
            tif_files, sync_results, results_path, behavior_sync_dir, block_size
        )
