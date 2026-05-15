"""Core synchronization logic for aligning tif frames to behavioral telemetry."""

import pickle
import re
import warnings
from pathlib import Path

import numpy as np
import pynapple as nap
import tifffile
from tqdm import tqdm

from totalsync_utils import decode_single_file


def extract_barcode_from_tif(tif_file: str) -> dict:
    tag_structure = {
        'image_description': 5,
        'frame_timestamp': 3,
        'auxTrigger0': 10,
    }

    with tifffile.TiffFile(tif_file) as tif:
        n_pages = len(tif.pages)
        ts = np.zeros(n_pages)
        value = np.zeros(n_pages)
        frame_n = np.zeros(n_pages)
        for i, page in tqdm(enumerate(tif.pages), total=n_pages):
            description = page.tags.values()[tag_structure['image_description']].value
            timestamp = float(
                description.split('\n')[tag_structure['frame_timestamp']].split('=')[-1]
            )
            aux_line = description.split('\n')[tag_structure['auxTrigger0']]
            data = aux_line.split('=')[-1].strip(' [').strip(']').strip(' ]')
            ts[i] = timestamp
            frame_n[i] = i
            if 0 < len(data) < 50:
                try:
                    value[i] = float(data)
                except ValueError:
                    pass

    return {'ts': ts, 'value': value, 'frame_n': frame_n}


def closest_match_indices_sorted(A, B, max_tolerance):
    """Return one-to-one closest matches between sorted arrays A and B."""
    A = np.asarray(A)
    B = np.asarray(B)

    i = 0
    j = 0

    match_A_indices = []
    match_B_indices = []
    match_A_values = []
    match_B_values = []
    match_abs_differences = []
    match_differences = []

    unmatched_A_indices = []
    matched_B_indices = set()

    import pandas as pd

    while i < len(A):
        a = A[i]

        while j < len(B) and B[j] < a - max_tolerance:
            j += 1

        candidates = []

        if j < len(B) and abs(B[j] - a) <= max_tolerance:
            candidates.append(j)

        if j > 0 and (j - 1) not in matched_B_indices:
            if abs(B[j - 1] - a) <= max_tolerance:
                candidates.append(j - 1)

        candidates = [idx for idx in candidates if idx not in matched_B_indices]

        if candidates:
            best_j = min(candidates, key=lambda idx: abs(B[idx] - a))

            match_A_indices.append(i)
            match_B_indices.append(best_j)
            match_A_values.append(A[i])
            match_B_values.append(B[best_j])
            match_abs_differences.append(abs(B[best_j] - A[i]))
            match_differences.append(B[best_j] - A[i])
            matched_B_indices.add(best_j)

            if best_j == j:
                j += 1
        else:
            unmatched_A_indices.append(i)

        i += 1

    unmatched_B_indices = np.array(
        [idx for idx in range(len(B)) if idx not in matched_B_indices], dtype=int
    )

    matches = pd.DataFrame({
        'A_index': np.array(match_A_indices, dtype=int),
        'B_index': np.array(match_B_indices, dtype=int),
        'A_value': np.array(match_A_values, dtype=A.dtype),
        'B_value': np.array(match_B_values, dtype=B.dtype),
        'abs_difference': np.array(match_abs_differences),
        'difference': np.array(match_differences),
    })

    return matches, np.array(unmatched_A_indices, dtype=int), unmatched_B_indices


def normalize_underscores(s: str) -> str:
    return re.sub(r'_+', '_', s).rstrip('_')


def fix_tsync_time(log_times: np.ndarray) -> np.ndarray:
    skips = -np.where(
        np.diff(log_times) < 0,
        np.diff(log_times) - np.median(np.diff(log_times)),
        0,
    )
    cs = np.cumsum(skips)
    cs2 = np.hstack((0, cs))
    return log_times + cs2


def synchronize(tif_file: str, b64_file: str, output_dir: str, pin_sheet_file: str) -> dict:
    """Synchronize a tif imaging file with a b64 behavioral telemetry file.

    Parameters
    ----------
    tif_file : str
        Path to the ScanImage tif recording.
    b64_file : str
        Path to the TotalSync .b64 behavioral telemetry file.
    output_dir : str
        Directory where output files will be saved.
    pin_sheet_file : str
        Path to the pin mapping JSON file.

    Returns
    -------
    dict
        Statistics and synchronization results with keys:
        - 'session': session name (stem of b64_file)
        - 'has_barcode': whether barcode-based alignment was used
        - 'max_ts_gap': maximum timestamp gap in the behavioral log
        - 'gap_locations': timestamps where gaps occurred
        - 'barcode_shift' (if has_barcode): time shift between barcode signals
        - 'barcode_frame_matches' (if has_barcode): DataFrame of matched frames
        - 'frames_time_idx': the resulting pynapple Tsd

    Saved files (in output_dir)
    ---------------------------
    {session}_barcode_data.npz
        Raw decoded telemetry arrays.
    {session}_frames_time_idx.npz
        Pynapple Tsd mapping scanner time -> tif frame index.
    {session}_behavior_sync_stats.pkl
        Dictionary of synchronization statistics.
    behavior/{key_name}.npz
        One pynapple Tsd (1-D channels) or TsdFrame (2-D channels) per decoded
        telemetry key, time-indexed by the corrected TotalSync clock (µs).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = Path(b64_file).stem
    stats = {'session': session}

    # --- Decode behavioral telemetry ---
    tsync_data = decode_single_file(b64_file, pin_json_path=pin_sheet_file)
    np.savez(output_dir / f"{session}_barcode_data.npz", **tsync_data)

    # --- Build frame-clock timestamps ---
    frame_clock = tsync_data['Scanner Frame Clock (Input)'].astype(int)
    log_times = tsync_data['startTS'].astype(int)

    onsets = np.nonzero(np.diff(frame_clock) == 1)[0] + 1

    stats['max_ts_gap'] = int(np.max(np.diff(log_times)))
    stats['gap_locations'] = log_times[np.where(np.diff(log_times) > 30000)]
    if len(stats['gap_locations']) > 0:
        warnings.warn(f"There are gaps in the timestamps: {stats['gap_locations']}")

    tsync_time = fix_tsync_time(log_times)

    # --- Save behavioral telemetry as pynapple objects ---
    behavior_dir = output_dir / "behavior"
    behavior_dir.mkdir(parents=True, exist_ok=True)
    for key in tsync_data:
        key_name = normalize_underscores(
            key.replace(" ", "_").replace("(", "_").replace(")", "_").replace("-", "_")
        )
        if tsync_data[key].ndim == 1:
            tsd = nap.Tsd(t=tsync_time, d=tsync_data[key], time_units='us')
            tsd.save(behavior_dir / f"{key_name}.npz")
        elif tsync_data[key].ndim == 2:
            tsd = nap.TsdFrame(t=tsync_time, d=tsync_data[key], time_units='us')
            tsd.save(behavior_dir / f"{key_name}.npz")

    t_frames = nap.Ts(tsync_time[onsets], time_units='us')

    # --- Extract aux barcode from tif ---
    aux_data = extract_barcode_from_tif(tif_file)

    aux_high = np.nonzero(aux_data['value'])[0]
    aux_barcode_ts = nap.Ts(aux_data['value'][aux_high], time_units='s')

    has_barcode = 'Barcode (Scanner)' in tsync_data and len(aux_barcode_ts) > 0
    stats['has_barcode'] = has_barcode

    if has_barcode:
        tsync_barcode = tsync_data['Barcode (Scanner)'].astype(int)
        tsync_barcode_rising_edge = np.nonzero(np.diff(tsync_barcode) > 0)[0] + 1
        tsync_barcode_ts = nap.Ts(tsync_time[tsync_barcode_rising_edge], time_units='us')

        barcode_group = nap.TsGroup({0: aux_barcode_ts, 1: tsync_barcode_ts})
        crosscorrs = nap.compute_crosscorrelogram(
            group=barcode_group, time_units='ms', windowsize=2000000, binsize=1
        )
        shift = crosscorrs.idxmax().iloc[0]
        stats['barcode_shift'] = float(shift)

        matches, _, _ = closest_match_indices_sorted(
            aux_data['ts'][aux_high] + shift, t_frames.t, max_tolerance=0.025
        )
        stats['barcode_frame_matches'] = matches

        frames_time_idx = nap.Tsd(
            t=matches['B_value'].to_numpy(),
            d=matches['A_index'].to_numpy(),
            time_units='s',
        )
    else:
        warnings.warn(
            "No barcode detected in the tif file, frame/time alignment will be done "
            "by assuming that the first Scanner frame clock pulse corresponds to the "
            "first tif frame"
        )
        if len(stats['gap_locations']) > 0:
            warnings.warn(
                "With no barcode, and gaps in the timestamps, alignment will be done "
                "up to the first gap"
            )
            # find the first gap location after the scanner was started
            align_stop = stats['gap_locations'][np.where(stats['gap_locations'] > t_frames[0].t * 1e6)[0][0]]
            ep = nap.IntervalSet(start=0, end=align_stop, time_units='us')
            t_frames = t_frames.restrict(ep)

        frames_time_idx = nap.Tsd(
            t=t_frames.t,
            d=np.arange(len(t_frames)),
            time_units='s',
        )

    frames_time_idx.save(output_dir / f"{session}_frames_time_idx.npz")

    stats['frames_time_idx'] = frames_time_idx

    with open(output_dir / f"{session}_behavior_sync_stats.pkl", 'wb') as f:
        pickle.dump({k: v for k, v in stats.items() if k != 'frames_time_idx'}, f)

    return stats
