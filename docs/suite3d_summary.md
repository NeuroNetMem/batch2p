Explore suite3d package structure and saved outputs

## Comprehensive Suite3D Package Exploration Report

### 1. OVERALL PACKAGE STRUCTURE AND PURPOSE

**Suite3D** is a volumetric 3D cell detection algorithm for multi-plane functional two-photon (2P) imaging. It's designed to identify and segment neurons across multiple imaging planes in 3D volumetric data.

**Main pipeline stages:**
1. **Initialization (`run_init_pass`)** - Loads sample data, calculates reference image, estimates crosstalk, fuse shifts
2. **Registration (`register`)** - Aligns movies to reference image in 3D
3. **Correlation Map (`calculate_corr_map`)** - Computes activity correlation map for cell detection
4. **Segmentation (`segment_rois`)** - Detects and segments individual cells
5. **Extraction & Deconvolution (`extract_and_deconvolve`)** - Extracts fluorescence traces and deconvolves spike trains

---

### 2. SAVED OUTPUT FILES - COMPREHENSIVE MAPPING

#### **DIRECTORY STRUCTURE**
```
job_dir (s3d-{job_id})/
├── dirs.npy                          # Dictionary mapping of all subdirectories
├── params.npy                         # Job parameters (dict)
├── log.txt                            # Execution log
├── summary/
│   ├── summary.npy                    # Init pass results (dict)
│   ├── init_mov.npy                   # Registered initialization movie
│   ├── params.npy                     # Copy of params from init pass
│   └── crosstalk_plots/               # Visualization files
├── registered_fused_data/             # Registration output
│   ├── {tif_name}.npy                 # Registered movie files (one per TIFF)
│   └── params.npy
├── corrmap/                           # Correlation map computation
│   ├── batch-**/                      # One per batch
│   │   ├── vmap.npy                   # Correlation map for batch
│   │   ├── vmap2.npy                  # Sum of squared correlations
│   │   ├── mean_img.npy               # Mean intensity
│   │   └── max_img.npy                # Maximum intensity
│   │   └── std2_img.npy               # Sum of squared standard deviations
│   └── params.npy
├── mov_sub/                           # Neuropil-subtracted movies
│   └── mov_sub-****.npy               # One per batch
├── segmentation/                      # Per-patch cell detection
│   ├── patch-****/                    # One per spatial patch
│   │   ├── stats.npy                  # Cell detection stats (list of dicts)
│   │   ├── info.npy                   # Patch info dict (vmap)
│   │   └── iscell.npy                 # Binary flags [n_cells, 2]
│   └── params.npy
├── rois/                              # Combined segmentation results
│   ├── stats.npy                      # All detected cells (n_cells,)
│   ├── stats_small.npy                # Stats without neuropil coordinates
│   ├── iscell.npy                     # Binary flags (n_cells, 2)
│   ├── info.npy                       # Summary info dict
│   ├── F.npy                          # Raw fluorescence traces (n_cells, n_frames)
│   ├── Fneu.npy                       # Neuropil fluorescence (n_cells, n_frames)
│   ├── spks.npy                       # Deconvolved spikes (n_cells, n_frames)
│   ├── iscell_extracted.npy           # Boolean flags after extraction
│   └── params.npy
└── iters/                             # Registration iteration files
```

---

### 3. DETAILED FILE DESCRIPTIONS

#### **Summary.npy (Dictionary - Init Pass Output)**
- **Location**: `summary/summary.npy`
- **Key variables and meanings**:
  - `ref_img_3d`: 3D reference image (nz, ny, nx) - the canonical target for registration
  - `raw_img`: Mean image (nz, ny, nx) directly from TIFF files (unprocessed)
  - `img`: Crosstalk-subtracted mean image (nz, ny, nx)
  - `plane_shifts`: (nz,) array - plane-to-plane shifts in pixels (for 3D alignment)
  - `refs_and_masks`: List of reference images and masks per plane
  - `plane_shifts_uncorrected`: Raw plane shifts before inter-plane correction
  - `crosstalk_coeff`: Float - estimated crosstalk coupling coefficient
  - `crosstalk_planes`: Planes used for crosstalk estimation
  - `crosstalk_info`: Dictionary with crosstalk estimation details
  - `min_pix_vals`: (nz,) minimum pixel values subtracted for positivity
  - `fuse_shift`: Int - optimal pixel shift for fusing multi-strip acquisitions
  - `fuse_shifts`: Array of fuse shifts per plane
  - `fuse_ccs`: Cross-correlation values for fuse shift optimization
  - `reference_params`: Dictionary of parameters used for reference calculation
  - `reference_info`: Additional reference computation metadata
  - `xpad`, `ypad`: Padding added to reference image
  - `new_xs`, `og_xs`: Strip boundaries after and before fusion
  - `tiffile_xs`: Original strip boundaries from TIFF
  - `init_tifs`: List of TIF files used for initialization
  - `init_mov_path`: Path to init_mov.npy

**Data types**: Mixed (ndarrays, floats, ints, lists, dicts)

---

#### **Registered Movie Files** (Numpy .npy arrays)
- **Location**: `registered_fused_data/{tif_name}.npy`
- **Shape**: (nz, nt, ny, nx) where:
  - nz = number of planes
  - nt = number of time frames
  - ny, nx = image height/width in pixels
- **Meaning**: Full 3D+time movie registered to reference image
- **Data type**: uint16 or float (as per processing)

---

#### **Correlation Map / Batch Results** (.npy arrays)
- **Location**: `corrmap/batch-***/`
- **Files per batch**:
  - `vmap.npy`: Correlation map (nz, ny, nx) - how correlated each voxel is with cell activity
  - `vmap2.npy`: Accumulator for computing vmap across all batches
  - `mean_img.npy`: Mean intensity volume (nz, ny, nx)
  - `max_img.npy`: Maximum intensity volume (nz, ny, nx)
  - `std2_img.npy`: Sum of squared standard deviations for variance estimation

**vmap meaning**: Values indicate activity correlation strength at each voxel, used for automated cell detection

---

#### **Neuropil-Subtracted Movie** (.npy arrays)
- **Location**: `mov_sub/mov_sub-****.npy`
- **Shape**: (nt, nz, ny, nx) - note TIME-FIRST ordering (different from registered)
- **Meaning**: Movie with neuropil contamination subtracted, used for final segmentation
- **Data type**: float32 or float16 (configurable)

---

#### **Cell Detection Stats** (.npy arrays)
- **Location**: `segmentation/patch-****/stats.npy` and `rois/stats.npy`
- **Contents**: List of dictionaries, one per detected cell
- **Key per-cell statistics**:
  - `idx`: Cell index within patch
  - `coords`: (z, y, x) coordinates in full volume
  - `coords_patch`: (z, y, x) coordinates within patch
  - `med`: (z, y, x) median position of cell
  - `med_patch`: Median position relative to patch
  - `lam`: Pixel weights for cell ROI (neuropil) - defines spatial footprint
  - `npcoords`: Neuropil pixel coordinates
  - `active_frames`: Array of frame indices where cell was active
  - `peak_val`: Peak correlation value at cell location
  - `patch_idx`: Which spatial patch this cell was detected in
  - `threshold`: Activity threshold used for detection

---

#### **iscell.npy** (.npy arrays)
- **Location**: `segmentation/patch-****/iscell.npy` and `rois/iscell.npy`
- **Shape**: (n_cells, 2) boolean array
- **Meaning**:
  - Column 0: Whether the ROI is a real cell (True) or artifact/neuropil (False)
  - Column 1: Confidence/probability of being a cell
- **Purpose**: Quality control and filtering of detected ROIs

---

#### **info.npy** (Dictionary)
- **Location**: `rois/info.npy` and `segmentation/patch-****/info.npy`
- **Contents** (top-level):
  - `vmap`: Correlation map (nz, ny, nx)
  - `vmap_raw`: Raw unthresholded correlation map (if local thresholding used)
  - `mean_img`: Mean image volume
  - `max_img`: Maximum image volume
  - `all_params`: Complete parameters dict used for analysis

---

#### **Fluorescence Traces** (.npy arrays)
- **Location**: `rois/F.npy`, `rois/Fneu.npy`
- **Shape**: (n_cells, n_frames)
- **Meaning**:
  - `F.npy`: Raw fluorescence traces - total fluorescence in cell ROI per frame
  - `Fneu.npy`: Neuropil fluorescence - fluorescence in surrounding neuropil per frame
- **Data type**: float32
- **Computation**: Weighted sum of movie intensities using cell's spatial footprint (lam)

---

#### **Deconvolved Spikes** (.npy arrays)
- **Location**: `rois/spks.npy`
- **Shape**: (n_cells, n_frames)
- **Meaning**: Estimated spike train - deconvolved activity from fluorescence
- **Algorithm**: OASIS (fast non-negative deconvolution) using:
  - `tau`: GCamp decay timescale (~1.3 for GCamp6s)
  - `fs`: Sampling rate (volumes/second)
- **Data type**: float32
- **Values**: Non-negative, represent inferred spike probability

---

#### **params.npy** (Dictionary)
- **Location**: Multiple locations (job_dir, summary, corrmap, rois, segmentation, iters)
- **Contents**: Complete parameter dictionary controlling the analysis
- **Key parameters**:
  - **Imaging**: `planes`, `n_ch_tif`, `fs`, `tau`, `voxel_size_um`
  - **Filtering**: `cell_filt_xy_um`, `cell_filt_z_um`, `npil_filt_xy_um`, `npil_filt_z_um`
  - **Detection**: `intensity_thresh`, `extend_thresh`, `detection_timebin`, `peak_thresh`
  - **Processing**: `t_batch_size`, `n_proc_corr`, `gpu_reg`, `3d_reg`
  - **Segmentation**: `patch_size_xy`, `patch_overlap_xy`, `segmentation_timebin`
  - **Extraction**: `npil_coeff`, `npil_to_roi_npix_ratio`, `min_npil_npix`
  - **Deconvolution**: `dcnv_baseline`, `dcnv_win_baseline`, `tau`, `fs`

---

### 4. KEY FUNCTIONS THAT WRITE/SAVE OUTPUTS

#### **init_pass.py**
```python
run_init_pass(job)
├─ Saves: summary.npy ← all reference images, shifts, crosstalk info
├─ Saves: init_mov.npy ← registered initialization movie
└─ Saves: params.npy copy in summary dir
```

#### **corrmap.py**
```python
save_batch_results(vmap_batch, accums, batch_dir)
├─ Saves: vmap.npy ← correlation map
├─ Saves: vmap2.npy ← sum of squared correlations
├─ Saves: mean_img.npy ← mean intensity
├─ Saves: max_img.npy ← max intensity
└─ Saves: std2_img.npy ← variance accumulator
```

#### **extension.py (Cell Detection)**
```python
detect_cells(patch, vmap, savepath=None)
├─ Saves: {savepath} ← stats.npy (checkpoints every 250 cells)
└─ Saves: iscell.npy ← cell quality flags
```

#### **job.py - Main Pipeline Methods**

```python
Job.register()
├─ Saves: registered_fused_data/{tif}.npy ← registered movies

Job.calculate_corr_map(mov, save=True)
├─ Saves: corrmap/batch-**/*.npy ← batch results
├─ Saves: mov_sub/mov_sub-****.npy ← neuropil-subtracted movies
└─ Saves: params.npy in corrmap dir

Job.segment_rois()
├─ Saves: segmentation/patch-****/stats.npy ← cell detection
├─ Saves: segmentation/patch-****/info.npy ← patch info
├─ Saves: rois/stats.npy ← combined cell stats (after combine_patches)
├─ Saves: rois/iscell.npy ← cell flags
├─ Saves: rois/info.npy ← combined info
└─ Saves: params.npy in both dirs

Job.extract_and_deconvolve()
├─ Saves: F.npy ← raw fluorescence traces
├─ Saves: Fneu.npy ← neuropil fluorescence
├─ Saves: spks.npy ← deconvolved spikes
└─ Saves: iscell_extracted.npy ← extraction quality flags

Job.export_results(export_path)
└─ Copies key results to export location:
   ├─ stats_small.npy
   ├─ info.npy
   ├─ F.npy
   ├─ Fneu.npy
   ├─ spks.npy
   ├─ iscell.npy
   ├─ s3d-params.npy
   └─ frames.npy (optional)
```

---

### 5. OUTPUT DIRECTORY CREATION FLOW

**Default directories created at job initialization:**
1. `summary/` - Init pass results
2. `registered_fused_data/` - Registration output
3. `iters/` - Registration iteration details (optional)

**Directories created during pipeline:**
4. `corrmap/` → `batch-**/` - Correlation map batches
5. `mov_sub/` - Neuropil-subtracted movies
6. `segmentation/` → `patch-****/` - Per-patch detection
7. `rois/` - Final combined results

**Optional:**
- `sweeps/{sweep_name}/comb_**/` - Parameter sweep results
- Extensions/ subdirs - Custom analysis outputs

---

### 6. DATA FLOW AND VARIABLE NAMING CONVENTIONS

**Spatial dimensions**: nz (planes), ny (y-pixels), nx (x-pixels)
**Temporal dimension**: nt (frames)
**Biological semantics**:
- **F** = Fluorescence (neural activity signal)
- **Fneu** = Neuropil fluorescence (local contamination)
- **spks** = Spikes (deconvolved action potential proxy)
- **vmap** = Correlation/activity map (cell-like activity strength)
- **lam** = Spatial footprint weights (pixel contributions to cell)
- **iscell** = Quality control flags

---

### 7. FILE FORMATS SUMMARY

| Format | Usage | Examples |
|--------|-------|---------|
| **.npy** | Primary output format | All arrays, dicts, and serialized data |
| **.npz** | Not heavily used | Optional for compressed storage |
| **.txt** | Logging | log.txt |
| **.png** | Visualization | crosstalk_plots/ |
