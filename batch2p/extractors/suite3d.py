"""Suite3D source extraction algorithm."""
import json
from pathlib import Path

import numpy as np

from .base import SourceExtractor


def _load_params(params_path: Path) -> dict:
    with open(params_path) as f:
        params = json.load(f)
    params.pop("comments", None)
    if "planes" in params:
        params["planes"] = np.array(params["planes"])
    if "pc_size" in params:
        params["pc_size"] = np.array(params["pc_size"])
    return params


def _params_to_json_serializable(params: dict) -> dict:
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in params.items()}


def _get_tif_n_frames(tif_path: Path) -> int:
    import tifffile
    with tifffile.TiffFile(tif_path) as tif:
        return len(tif.pages)


def create_synced_outputs(
    tif_files: list[Path],
    sync_results: list[dict],
    rois_dir: Path,
    behavior_sync_dir: Path,
    block_size: int = 3,
) -> None:
    """Select suite3d traces by synced frame indices and save as pynapple TsdFrames.

    For each session, loads F, Fneu, and spks from rois_dir, selects the columns
    corresponding to synchronized frames (using frames_time_idx.d plus the cumulative
    frame offset for that TIF), and saves a pynapple TsdFrame per array as
    F_sync.npz, Fneu_sync.npz, spks_sync.npz in behavior_sync_dir.
    """
    import pynapple as nap

    arrays_to_sync = {}
    for name in ('F', 'Fneu', 'spks'):
        npy_path = rois_dir / f"{name}.npy"
        if npy_path.exists():
            arrays_to_sync[name] = np.load(npy_path)

    if not arrays_to_sync:
        print("  No F/Fneu/spks arrays found in rois directory, skipping synced outputs.")
        return

    frame_offsets = [0]
    for tif in tif_files[:-1]:
        frame_offsets.append(frame_offsets[-1] + _get_tif_n_frames(tif))

    time_offsets = [0]
    for stats in sync_results:
        time_offsets.append(time_offsets[-1] + stats['frames_time_idx'].t[-1])

    for i, stats in enumerate(sync_results):
        stats['time_offsets'] = time_offsets[i]

    for tif, stats, offset, time_offset in zip(tif_files, sync_results, frame_offsets, time_offsets):
        frames_time_idx = stats['frames_time_idx']
        local_indices = frames_time_idx.d.astype(int)

        if block_size > 1:
            local_indices = np.unique((local_indices / block_size).astype(int))
            t_frames = frames_time_idx.t[local_indices * block_size]
        else:
            t_frames = frames_time_idx.t
        global_indices = local_indices
        t_frames = t_frames + time_offset

        for name, arr in arrays_to_sync.items():
            global_indices = global_indices[np.where(global_indices < arr.shape[1])]
            selected = arr[:, global_indices]  # (n_cells, n_selected_frames)
            t = t_frames[:len(global_indices)]
            tsd_frame = nap.TsdFrame(t=t, d=selected.T, time_units='s')
            out_path = behavior_sync_dir / f"{name}_sync.npz"
            tsd_frame.save(out_path)
            print(f"    Saved {out_path.name} ({tsd_frame.shape})")


class Suite3DExtractor(SourceExtractor):
    def __init__(self, data: dict):
        super().__init__(data)
        params_file = Path(data["params_file"])
        if not params_file.is_absolute():
            params_file = Path(data.get("root_path", ".")) / params_file
        self.params = _load_params(params_file)

    def get_job_subdir(self, job_id: str) -> str:
        return f"s3d-{job_id}"

    def save_reproducibility_info(self, results_path: Path) -> None:
        saved_params = _params_to_json_serializable(self.params)
        with open(results_path / "params_used.json", "w") as f:
            json.dump(saved_params, f, indent=2)

    def run(self, tifs: list[Path], job_root_dir: Path, job_id: str, results_path: Path) -> None:
        from suite3d.job import Job

        job = Job(job_root_dir, job_id, tifs=tifs,
                  params=self.params, create=True, overwrite=True, verbosity=3)
        job.params.update(self.params)
        job.run_init_pass()
        job.register()
        job.calculate_corr_map()
        job.segment_rois()
        job.compute_npil_masks()
        job.extract_and_deconvolve()
        job.export_results(results_path, result_dir_name="rois")

    def create_synced_outputs(
        self,
        tif_files: list[Path],
        sync_results: list[dict],
        results_path: Path,
        behavior_sync_dir: Path,
        block_size: int,
    ) -> None:
        rois_dir = results_path / f"s3d-results-{results_path.name}"
        create_synced_outputs(tif_files, sync_results, rois_dir, behavior_sync_dir, block_size)
