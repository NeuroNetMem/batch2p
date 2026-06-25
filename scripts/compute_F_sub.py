#!/usr/bin/env python3
"""Compute baseline-subtracted neuropil-corrected fluorescence (F_sub.npy).

Looks for F.npy and Fneu.npy in the current directory and writes F_sub.npy
to the same directory.

  F_sub = dcnv.preprocess(F - neucoeff * Fneu)

Parameters are read from a params.json file supplied via --params-file.
The JSON may use the same two-level structure as suite2p batch params:
  - 'extraction:' section: neuropil_coefficient  (fallback: 'neucoeff', default 0.7)
  - 'dcnv_preprocess' section: baseline, win_baseline, sig_baseline,
                                prctile_baseline  (fallbacks from flat keys)
  - flat keys: fs, batch_size, torch_device

With --normalise, also computes dF/F from F_sub and writes dFF.npy:

  dFF = (F_sub - F0) / F0

where F0 is a rolling percentile baseline (percentile_filter). Options
--dff-window-sec, --dff-percentile, and --dff-abs-floor control the
computation.
"""
import argparse
import json
from pathlib import Path

import numpy as np


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


def compute_F_sub(work_dir: Path, settings: dict) -> np.ndarray:
    import torch
    from suite2p.extraction import dcnv

    f_path = work_dir / "F.npy"
    fneu_path = work_dir / "Fneu.npy"

    if not f_path.exists():
        raise FileNotFoundError(f"F.npy not found in {work_dir}")
    if not fneu_path.exists():
        raise FileNotFoundError(f"Fneu.npy not found in {work_dir}")

    F = np.load(f_path)
    Fneu = np.load(fneu_path)

    extraction = settings.get('extraction:', {})
    neucoeff = float(extraction.get('neuropil_coefficient', settings.get('neucoeff', 0.7)))
    print(f"neuropil_coefficient: {neucoeff}")
    Fc = F - neucoeff * Fneu

    dcnv_section = settings.get('dcnv_preprocess', {})
    def _p(key, default):
        return dcnv_section.get(key, settings.get(key, default))

    torch_device = settings.get('torch_device') or _detect_torch_device()
    device = torch.device(torch_device)
    print(f"torch_device: {torch_device}")

    F_sub = dcnv.preprocess(
        F=Fc,
        baseline=_p('baseline', 'maximin'),
        win_baseline=float(_p('win_baseline', 60.0)),
        sig_baseline=float(_p('sig_baseline', 10.0)),
        fs=float(settings.get('fs', 10.0)),
        prctile_baseline=float(_p('prctile_baseline', 8.0)),
        batch_size=int(settings.get('batch_size', 200)),
        device=device,
    )

    out_path = work_dir / "F_sub.npy"
    np.save(out_path, F_sub)
    print(f"Saved {out_path}  shape={F_sub.shape}")
    return F_sub


def compute_dff(f_sub, fs=29.96, window_sec=300, percentile=8, abs_floor=10):
    from scipy.ndimage import percentile_filter
    window_frames = int(window_sec * fs)
    f0 = percentile_filter(f_sub, percentile, size=window_frames, mode='nearest')
    f0_clamped = np.maximum(f0, abs_floor)
    dff = (f_sub - f0_clamped) / f0_clamped
    return dff, f0_clamped


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--params-file', required=True, type=Path,
                        help='Path to params.json')
    parser.add_argument('--normalise', '--normalize', action='store_true',
                        help='Also compute dF/F from F_sub and save as dFF.npy.')
    parser.add_argument('--dff-window-sec', type=float, default=300,
                        help='Rolling baseline window in seconds for dF/F (default: 300).')
    parser.add_argument('--dff-percentile', type=float, default=8,
                        help='Percentile used for the F0 baseline estimate (default: 8).')
    parser.add_argument('--dff-abs-floor', type=float, default=10,
                        help='Absolute fluorescence floor clamped onto F0 (default: 10).')
    args = parser.parse_args()

    params_file = args.params_file
    if not params_file.exists():
        parser.error(f"params file not found: {params_file}")

    with open(params_file) as f:
        settings = json.load(f)
    settings.pop('comments', None)

    work_dir = Path.cwd()
    print(f"Working directory: {work_dir}")
    F_sub = compute_F_sub(work_dir, settings)

    if args.normalise:
        fs = float(settings.get('fs', 10.0))
        print(f"Computing dF/F  (window={args.dff_window_sec}s, "
              f"percentile={args.dff_percentile}, abs_floor={args.dff_abs_floor}, fs={fs})")
        dff, _ = compute_dff(F_sub, fs=fs,
                             window_sec=args.dff_window_sec,
                             percentile=args.dff_percentile,
                             abs_floor=args.dff_abs_floor)
        dff_path = work_dir / "dFF.npy"
        np.save(dff_path, dff)
        print(f"Saved {dff_path}  shape={dff.shape}")


if __name__ == '__main__':
    main()
