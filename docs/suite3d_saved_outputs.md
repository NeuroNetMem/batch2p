# Suite3D: Saved Output Overview

Suite3D is a volumetric 3D cell detection pipeline for multi-plane two-photon calcium imaging. It segments neurons across imaging planes and extracts fluorescence traces.

---

## Directory Structure

```
s3d-{job_id}/
├── params.npy                    # Job parameters (dict)
├── summary/                      # Init pass results
├── registered_fused_data/        # Registered movies
├── corrmap/batch-**/             # Correlation map batches
├── mov_sub/                      # Neuropil-subtracted movies
├── segmentation/patch-****/      # Per-patch cell detection
└── rois/                         # Final combined results (primary output)
```

---

## Primary Outputs (`rois/`)

| File | Shape | Dtype | Meaning |
|------|-------|-------|---------|
| `F.npy` | `(n_cells, n_frames)` | float32 | Raw fluorescence traces — weighted sum of pixel intensities within each cell's spatial footprint |
| `Fneu.npy` | `(n_cells, n_frames)` | float32 | Neuropil fluorescence — contaminating signal from surrounding tissue |
| `spks.npy` | `(n_cells, n_frames)` | float32 | Deconvolved spike estimates (OASIS algorithm); non-negative, proxy for action potentials |
| `iscell.npy` | `(n_cells, 2)` | bool/float | Col 0: is it a real cell? Col 1: confidence score |
| `stats.npy` | list of `n_cells` dicts | — | Per-cell spatial statistics (see below) |
| `stats_small.npy` | list of `n_cells` dicts | — | Same as stats but without neuropil coordinates (lighter weight) |
| `info.npy` | dict | — | Summary metadata: `vmap`, `mean_img`, `max_img`, full params |

---

## Per-Cell `stats` Dictionary (one entry per detected cell)

| Key | Meaning |
|-----|---------|
| `coords` | `(z, y, x)` pixel coordinates of the cell in the full volume |
| `med` | `(z, y, x)` median position of the cell |
| `lam` | Spatial footprint weights — pixel-level contributions to the cell's signal |
| `npcoords` | Neuropil pixel coordinates used for `Fneu` estimation |
| `active_frames` | Frame indices where the cell was detected as active |
| `peak_val` | Peak correlation value at the cell's location in `vmap` |
| `patch_idx` | Which spatial patch the cell was detected in |
| `threshold` | Activity threshold used during detection |

---

## Intermediate Outputs

### Init pass (`summary/summary.npy` — dict)

| Key | Meaning |
|-----|---------|
| `ref_img_3d` | `(nz, ny, nx)` — 3D reference image used for registration |
| `raw_img` | Mean image before crosstalk correction |
| `img` | Mean image after crosstalk correction |
| `plane_shifts` | `(nz,)` — inter-plane pixel shifts for 3D alignment |
| `crosstalk_coeff` | Estimated crosstalk coupling coefficient |
| `fuse_shift` | Optimal pixel shift for fusing multi-strip acquisitions |

### Registered movies (`registered_fused_data/{tif_name}.npy`)

- Shape: `(nz, nt, ny, nx)` — full 4D registered movie per TIFF file

### Correlation map (`corrmap/batch-**/`)

| File | Meaning |
|------|---------|
| `vmap.npy` | `(nz, ny, nx)` — activity correlation map; high values = cell-like activity |
| `mean_img.npy` | `(nz, ny, nx)` — mean intensity volume |
| `max_img.npy` | `(nz, ny, nx)` — maximum intensity volume |

### Neuropil-subtracted movies (`mov_sub/mov_sub-****.npy`)

- Shape: `(nt, nz, ny, nx)` — note time-first axis order (different from registered movies)

---

## Key Notes

- **All files are `.npy`** — dicts are saved with `np.save(..., allow_pickle=True)` and loaded with `np.load(..., allow_pickle=True).item()`
- **Spatial convention**: `(nz, ny, nx)` = (planes, y-pixels, x-pixels)
- **`vmap`** is the central intermediate result: it encodes how "cell-like" each voxel is and drives segmentation
- **`lam`** is the spatial footprint for each cell — it weights pixel contributions to `F` and `Fneu`
- The neuropil-corrected trace is computed externally as `F - npil_coeff * Fneu` (not saved directly; standard suite2p convention)
