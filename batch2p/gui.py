#!/usr/bin/env python3
"""batch2p GUI — visual configurator for batch2p data.json and params.json files.

Usage:
    batch2p-gui
    python -m batch2p.gui
"""

import ast
import copy
import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QApplication, QButtonGroup, QCheckBox,
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QSplitter, QStatusBar, QTabWidget,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QTextBrowser, QToolBar,
    QVBoxLayout, QWidget,
)

# ─── Parameter definitions ────────────────────────────────────────────────────
# Each entry: (section, name, default, description)
# section=None → top-level key in the JSON (suite2p flat params or suite3d all params)

S2P_PARAMS = [
    # Top-level (flat) suite2p settings
    (None, "tau",              1.0,        "Timescale for deconvolution and binning, in seconds."),
    (None, "fs",               10.0,       "Sampling rate per plane (Hz)."),
    (None, "nplanes",          1,          "Each tiff/file has this many planes in sequence."),
    (None, "nchannels",        1,          "Specify one- (1) or two-channel (2) recording."),
    (None, "functional_chan",  1,          "Channel used to extract functional ROIs (1-based)."),
    (None, "torch_device",     "cuda",     "Torch device: 'cuda' for GPU or 'cpu' for CPU. Auto-detected if omitted."),
    (None, "force_sktiff",     False,      "Use tifffile for TIFF reading instead of ScanImage TIFF reader."),
    (None, "ignore_flyback",   [],         "List of plane indices (0-based) to skip during processing."),
    (None, "keep_movie_raw",   False,      "Keep the binary file of non-registered frames."),
    (None, "diameter",         [12, 12],   "ROI diameter in [Y, X] pixels for sourcery/cellpose detection."),
    # run
    ("run", "do_registration",    1,     "Whether to motion-register data (2 forces re-registration)."),
    ("run", "do_detection",       True,  "Whether to run ROI detection and extraction."),
    ("run", "do_deconvolution",   True,  "Whether to run spike deconvolution."),
    ("run", "multiplane_parallel",False, "Run each plane as a separate server job."),
    # io
    ("io", "combined",      True,  "Combine all planes into a single result after processing."),
    ("io", "save_mat",      False, "Save output as MATLAB .mat file."),
    ("io", "delete_bin",    False, "Delete the binary file after processing."),
    ("io", "move_bin",      False, "Move binary to save_path if fast_disk differs from save_path."),
    # registration
    ("registration", "two_step_registration", False, "Run registration twice — useful for low-SNR data. Set keep_movie_raw=True when using this."),
    ("registration", "nimg_init",       400,       "Subsampled frames used to build the reference image. Increase if reference looks poor."),
    ("registration", "batch_size",      100,       "Frames per registration batch. Reduce if GPU runs out of memory."),
    ("registration", "maxregshift",     0.1,       "Max allowed shift as a fraction of frame max(width, height)."),
    ("registration", "nonrigid",        True,      "Use non-rigid (block-based) registration."),
    ("registration", "maxregshiftNR",   5,         "Maximum pixel shift for each non-rigid block, relative to the rigid shift."),
    ("registration", "block_size",      [128, 128],"Block size for non-rigid registration. Keep as a multiple of 2, 3, and/or 5."),
    ("registration", "smooth_sigma",    1.15,      "Gaussian smoothing in XY. ~1 is good for 2P; 3–5 may work for 1P."),
    ("registration", "smooth_sigma_time",0,        "Gaussian smoothing in time before computing registration shifts. Useful for low SNR."),
    ("registration", "th_badframes",    1.0,       "Frames with displacement above this × median are excluded from cropping estimate."),
    ("registration", "norm_frames",     True,      "Normalise frames when detecting shifts."),
    ("registration", "snr_thresh",      1.2,       "Non-rigid blocks below this SNR are smoothed. Set to 1.0 to disable smoothing."),
    ("registration", "subpixel",        10,        "Subpixel precision: 1/subpixel steps."),
    ("registration", "reg_tif",         False,     "Save registered TIFFs to disk."),
    ("registration", "reg_tif_chan2",   False,     "Save registered TIFFs for channel 2."),
    # detection
    ("detection", "denoise",            False,     "Use PCA denoising before cell detection."),
    ("detection", "block_size",         [64, 64],  "Block size for PCA denoising."),
    ("detection", "nbins",              5000,      "Max number of binned frames for detection. Reduce if RAM is limited."),
    ("detection", "highpass_time",      100,       "Running-mean subtraction window (bins). Use low values for 1P data."),
    ("detection", "threshold_scaling",  1.0,       "Multiplier for the auto-determined detection threshold. Lower = more cells."),
    ("detection", "max_overlap",        0.75,      "ROIs sharing more than this fraction of pixels with another ROI are discarded."),
    ("detection", "soma_crop",          True,      "Crop dendrites from ROI when computing npix_norm and compactness."),
    # classification
    ("classification", "use_builtin_classifier", False, "Use the built-in classifier instead of the user-trained one."),
    ("classification", "preclassify",            0.0,   "Drop ROIs with classifier score below this before extraction."),
    # extraction
    ("extraction", "neuropil_extract",      True,  "Extract neuropil signal. If False, Fneu is set to zero."),
    ("extraction", "neuropil_coefficient",  0.7,   "Neuropil subtraction coefficient (F_corrected = F − coeff × Fneu)."),
    ("extraction", "inner_neuropil_radius", 2,     "Pixels excluded from neuropil mask immediately adjacent to the ROI."),
    ("extraction", "min_neuropil_pixels",   350,   "Minimum number of pixels in the per-ROI neuropil mask."),
    ("extraction", "lam_percentile",        50.0,  "Percentile of ROI λ weights below which pixels are excluded from neuropil."),
    ("extraction", "allow_overlap",         False, "Allow shared pixels between overlapping ROIs (True) or discard them (False)."),
    # dcnv_preprocess
    ("dcnv_preprocess", "baseline",         "maximin","Baseline estimation method: 'maximin', 'prctile', or 'constant'."),
    ("dcnv_preprocess", "win_baseline",     60.0,   "Window length (seconds) for the max filter in maximin baseline."),
    ("dcnv_preprocess", "sig_baseline",     10.0,   "Width of Gaussian filter in frames applied before/after the max filter."),
    ("dcnv_preprocess", "prctile_baseline", 8.0,    "Percentile of trace used as baseline when method='prctile'."),
]

S3D_PARAMS = [
    # Mandatory
    ("Mandatory", "fs",                    2.8,            "Volume rate (Hz)."),
    ("Mandatory", "tau",                   1.3,            "GCaMP decay timescale in seconds. GCaMP6s ≈ 1.3, GCaMP6f ≈ 0.7."),
    ("Mandatory", "planes",                "np.arange(0,30)", "Plane indices to analyse (0 = deepest). Passed as a Python/numpy expression."),
    ("Mandatory", "n_ch_tif",              30,             "Number of planes recorded per volume in the TIFF."),
    ("Mandatory", "lbm",                   True,           "Data from light-bead microscopy (LBM). Set False for standard multiplane 2P."),
    ("Mandatory", "voxel_size_um",         [15, 2.5, 2.5], "Voxel size in microns [z, y, x]."),
    ("Mandatory", "num_colors",            1,              "Number of colour channels recorded (non-LBM only)."),
    ("Mandatory", "functional_color_channel", 0,           "0-based index of the functional colour channel (non-LBM only)."),
    # Initialization
    ("Initialization", "n_init_files",     1,     "Number of TIFFs used in the initialisation step (~1 min of data is usually enough)."),
    ("Initialization", "init_n_frames",    500,   "Random frames sampled from init files. Set None to use all frames."),
    ("Initialization", "subtract_crosstalk", True,"Subtract optical crosstalk between plane pairs separated by cavity_size planes."),
    ("Initialization", "cavity_size",      15,    "Number of planes separating a crosstalk pair (LBM-specific)."),
    # Registration
    ("Registration", "3d_reg",             True,      "Use 3-D volumetric registration."),
    ("Registration", "gpu_reg",            True,      "Use GPU for registration."),
    ("Registration", "fuse_strips",        True,      "Fuse mesoscope strip ROIs before registration."),
    ("Registration", "max_rigid_shift_pix",100,       "Maximum rigid shift in pixels. Must exceed any expected inter-plane LBM shift."),
    ("Registration", "nonrigid",           False,     "Use non-rigid registration (2-D; computationally expensive)."),
    ("Registration", "block_size",         [128, 128],"Non-rigid registration block size in [y, x] pixels."),
    ("Registration", "smooth_sigma",       1.15,      "Gaussian smoothing parameter for registration."),
    ("Registration", "snr_thresh",         1.2,       "SNR threshold for non-rigid blocks (2-D registration)."),
    ("Registration", "pc_size",            [2, 40, 40],"Phase-correlation search range in [z, y, x] pixels."),
    # Correlation Map / Segmentation
    ("Corr Map", "cell_filt_xy_um",        5,     "XY radius of the cell detection filter in microns."),
    ("Corr Map", "cell_filt_z_um",         10,    "Z extent of the cell detection filter in microns."),
    ("Corr Map", "npil_filt_xy_um",        100.0, "XY radius of the neuropil subtraction filter in microns."),
    ("Corr Map", "npil_filt_z_um",         15.0,  "Z extent of the neuropil subtraction filter in microns."),
    ("Corr Map", "peak_thresh",            0.1,   "Correlation-map peak threshold for cell detection. Lower = more cells found."),
    ("Corr Map", "extend_thresh",          0.05,  "Threshold to extend an ROI to a neighbouring pixel. Lower = larger ROIs."),
    ("Corr Map", "activity_thresh",        5.0,   "Only timepoints above this value (SD units) are used for segmentation."),
    ("Corr Map", "max_iter",               10000, "Maximum number of ROIs detected per patch."),
    ("Corr Map", "allow_overlap",          False, "Allow pixel overlap between ROIs."),
    ("Corr Map", "t_batch_size",           800,   "Timepoints processed per batch (must be a multiple of temporal_hpf)."),
    ("Corr Map", "temporal_hpf",           200,   "Temporal high-pass filter width (timepoints). Must divide t_batch_size evenly."),
    # SVD
    ("SVD", "n_svd_comp",                  600,        "SVD components computed per block."),
    ("SVD", "svd_block_shape",             [4, 200, 200],"Block shape for SVD denoising [z, y, x]."),
    # Deconvolution
    ("Deconvolution", "npil_coeff",        0.7,        "Neuropil subtraction coefficient."),
    ("Deconvolution", "dcnv_baseline",     "maximin",  "Baseline method: 'maximin', 'prctile', or 'constant'."),
    ("Deconvolution", "dcnv_win_baseline", 60,         "Window length (seconds) for maximin baseline."),
    ("Deconvolution", "dcnv_sig_baseline", 10,         "Gaussian filter width in frames."),
    ("Deconvolution", "dcnv_prctile_baseline", 8,      "Baseline percentile (used when dcnv_baseline='prctile')."),
    ("Deconvolution", "split_tif_size",    100,        "Internal: split registered data into chunks of this many frames."),
]

# ─── Run-config (data.json) field definitions ────────────────────────────────
# (key, label, default, widget_type, tooltip, shown_for)
# widget_type: "text" | "path" | "file" | "int" | "bool"
# shown_for:   "both" | "suite2p" | "suite3d"
DATA_FIELDS = [
    ("job_id",           "Job ID",              "",    "text", "Unique identifier for this run (used as output subdirectory name).", "both"),
    ("job_root_dir",     "Job Root Dir",        "",    "path", "Directory where Suite3D creates its job folder. Not used by Suite2P.", "both"),
    ("results_root_dir", "Results Root Dir",    "",    "path", "Parent directory for the <job_id> results folder.", "both"),
    ("temp_dir",         "Temp / Scratch Dir",  "",    "path", "Parent for the fast-disk scratch directory (Suite2P) or TIFF-split temp dir (Suite3D).", "both"),
    ("working_dir",      "Working Dir",         "",    "path", "Isolate all work in a temp subdirectory here and copy results back on completion (optional).", "both"),
    ("block_size",       "Block Size (planes/vol)", "3","int", "Planes per imaging volume; used for frame-index normalisation during behavioural sync.", "both"),
    ("fill_tsync_gaps",  "Fill TSync Gaps",     False, "bool", "Interpolate timestamp gaps in the behavioural log instead of truncating.", "both"),
    ("ignore_barcode",   "Ignore Barcode",      False, "bool", "Skip barcode-based alignment and fall back to frame-clock onset matching.", "both"),
    ("pinsheet_file",    "Pinsheet File",       "",    "file", "Path to the TotalSync pin-mapping JSON (required when behavioural data is provided).", "both"),
    ("tiff_trim_size",   "TIFF Trim Size",      "9999","int",  "Split each input TIFF into chunks of this many frames before processing. Set 0 to disable.", "both"),
    ("add_offset",       "Add Offset",          False, "bool", "Pass add_offset=True to split_3d_tiff_into_chunks when TIFF splitting is enabled.", "both"),
    ("do_F_sub",         "Compute F_sub",       False, "bool", "After extraction, compute F_sub = dcnv.preprocess(F - neucoeff*Fneu) and save as F_sub.npy. Also synchronized when behavioural sync is run. Uses baseline/neucoeff/fs params from the Suite2P params file.", "suite2p"),
    ("comments",         "Comments",            "",    "textarea", "Free-form notes about this run configuration. Ignored by batch2p and extractors.", "both"),
]

# ─── Utilities ────────────────────────────────────────────────────────────────

def safe_eval(expr: str):
    """Evaluate a Python/numpy expression safely. Returns the Python object."""
    expr = expr.strip()
    try:
        return ast.literal_eval(expr)
    except Exception:
        pass
    ns = {"np": np, "numpy": np, "arange": np.arange, "array": np.array,
          "linspace": np.linspace, "logspace": np.logspace, "True": True,
          "False": False, "None": None}
    return eval(expr, {"__builtins__": {}}, ns)


def value_to_str(v) -> str:
    """Represent a default parameter value as an editable string."""
    if isinstance(v, np.ndarray):
        return repr(v.tolist())
    if isinstance(v, (list, tuple)):
        return repr(list(v))
    if isinstance(v, str):
        return repr(v)
    return str(v)


def make_json_serializable(v):
    """Recursively convert numpy types/arrays to JSON-serialisable Python objects."""
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, dict):
        return {k: make_json_serializable(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [make_json_serializable(x) for x in v]
    return v


def _apply_template_vars(obj, variables: dict):
    """Recursively replace {{ var }} placeholders in string values.

    Only substitutes a placeholder when the corresponding variable is non-empty;
    otherwise the placeholder is left verbatim in the output.
    """
    if isinstance(obj, str):
        def _replace(m):
            name = m.group(1).strip()
            val = variables.get(name)
            return val if val else m.group(0)
        return re.sub(r'\{\{\s*(\w+)\s*\}\}', _replace, obj)
    if isinstance(obj, dict):
        return {k: _apply_template_vars(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_template_vars(x, variables) for x in obj]
    return obj


# ─── FileListWidget ───────────────────────────────────────────────────────────

class FileListWidget(QWidget):
    """Labeled list with Add / Remove / Move-Up / Move-Down buttons."""

    order_changed = pyqtSignal()

    def __init__(self, label: str, file_filter: str, root_path_getter=None, parent=None):
        super().__init__(parent)
        self._filter = file_filter
        self._root_path_getter = root_path_getter  # callable () -> str, or None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self._btn_add    = QPushButton("Add…")
        self._btn_remove = QPushButton("Remove")
        self._btn_up     = QPushButton("▲")
        self._btn_down   = QPushButton("▼")
        for btn in (self._btn_add, self._btn_remove, self._btn_up, self._btn_down):
            btn.setFixedHeight(26)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_files)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_up.clicked.connect(self._move_up)
        self._btn_down.clicked.connect(self._move_down)

    # ── public API ────────────────────────────────────────────────────────────

    def paths(self) -> list[str]:
        return [self.list_widget.item(i).data(Qt.UserRole)
                for i in range(self.list_widget.count())]

    def set_paths(self, paths: list[str]):
        self.list_widget.clear()
        for p in paths:
            self._append(p)
        self.order_changed.emit()

    def count(self) -> int:
        return self.list_widget.count()

    def current_row(self) -> int:
        return self.list_widget.currentRow()

    # ── internals ─────────────────────────────────────────────────────────────

    def _append(self, path: str):
        """Append *path* to the list. *path* should already be a relative path."""
        item = QListWidgetItem(path)
        item.setData(Qt.UserRole, path)
        item.setToolTip(path)
        self.list_widget.addItem(item)

    @staticmethod
    def _to_relative(path: str, root_str: str) -> str:
        """Return *path* relative to *root_str* when possible, else return just the filename."""
        if not root_str:
            return path
        try:
            return str(Path(path).relative_to(root_str))
        except ValueError:
            return Path(path).name

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files",
                                                 "", self._filter)
        root_str = self._root_path_getter() if self._root_path_getter else ""
        for p in paths:
            self._append(self._to_relative(p, root_str))
        self.order_changed.emit()

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.order_changed.emit()

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)
            self.order_changed.emit()

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)
            self.order_changed.emit()


# ─── InputFilesWidget ─────────────────────────────────────────────────────────

class InputFilesWidget(QWidget):
    """Left panel: root path, paired TIFF + .b64 lists, save/load."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── Root path ─────────────────────────────────────────────────────────
        root_box = QGroupBox("Root Path  (for server transfer — may differ from actual file location)")
        root_layout = QHBoxLayout(root_box)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("/data/ofl_2p/YYYYMMDD")
        btn_root = QPushButton("Browse…")
        btn_root.setFixedWidth(80)
        btn_root.clicked.connect(self._browse_root)
        root_layout.addWidget(self.root_edit)
        root_layout.addWidget(btn_root)
        layout.addWidget(root_box)

        # ── File lists ────────────────────────────────────────────────────────
        lists_splitter = QSplitter(Qt.Horizontal)
        self.tif_list = FileListWidget("TIFF files", "TIFF files (*.tif *.tiff)",
                                       root_path_getter=self.root_path)
        self.b64_list = FileListWidget(".b64 files (optional)", "b64 files (*.b64)",
                                       root_path_getter=self.root_path)
        lists_splitter.addWidget(self.tif_list)
        lists_splitter.addWidget(self.b64_list)
        lists_splitter.setSizes([300, 300])
        layout.addWidget(lists_splitter)

        # Sync selection: highlight matching row in the other list
        self.tif_list.list_widget.currentRowChanged.connect(
            lambda r: self.b64_list.list_widget.setCurrentRow(r))
        self.b64_list.list_widget.currentRowChanged.connect(
            lambda r: self.tif_list.list_widget.setCurrentRow(r))

        # Mismatch warning
        self._mismatch_label = QLabel("")
        self._mismatch_label.setStyleSheet("color: #cc4400;")
        layout.addWidget(self._mismatch_label)
        for lst in (self.tif_list, self.b64_list):
            lst.order_changed.connect(self._check_counts)

        # ── Save / Load ───────────────────────────────────────────────────────
        io_row = QHBoxLayout()
        btn_save = QPushButton("Save file list…")
        btn_load = QPushButton("Load file list…")
        btn_save.clicked.connect(self._save_file_list)
        btn_load.clicked.connect(self._load_file_list)
        io_row.addStretch()
        io_row.addWidget(btn_load)
        io_row.addWidget(btn_save)
        layout.addLayout(io_row)

    # ── public API ────────────────────────────────────────────────────────────

    def root_path(self) -> str:
        return self.root_edit.text().strip()

    def to_dict(self) -> dict:
        return {
            "root_path": self.root_path(),
            "tif_files": self.tif_list.paths(),
            "b64_files": self.b64_list.paths(),
        }

    def from_dict(self, d: dict):
        self.root_edit.setText(d.get("root_path", ""))
        self.tif_list.set_paths(d.get("tif_files", []))
        self.b64_list.set_paths(d.get("b64_files", []))

    # ── internals ─────────────────────────────────────────────────────────────

    def _browse_root(self):
        path = QFileDialog.getExistingDirectory(self, "Select root path")
        if path:
            self.root_edit.setText(path)

    def _check_counts(self):
        n_tif = self.tif_list.count()
        n_b64 = self.b64_list.count()
        if n_b64 > 0 and n_b64 != n_tif:
            self._mismatch_label.setText(
                f"⚠  {n_tif} TIFF files but {n_b64} .b64 files — counts must match for behavioural sync.")
        else:
            self._mismatch_label.setText("")

    def _save_file_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save file list",
                                               "", "JSON (*.json)")
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def _load_file_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load file list",
                                               "", "JSON (*.json)")
        if not path:
            return
        with open(path) as f:
            self.from_dict(json.load(f))


# ─── ParamTableWidget ─────────────────────────────────────────────────────────

_SECTION_COLOR   = QColor("#e8edf4")
_SWEEP_COLOR     = QColor("#d6ecff")
_SWEEP_HDR_COLOR = QColor("#4a90d9")

class ParamTableWidget(QWidget):
    """Parameter table with value editing, sweep checkboxes, and a description pane."""

    sweep_changed = pyqtSignal()

    COL_SECTION = 0
    COL_NAME    = 1
    COL_VALUE   = 2
    COL_SWEEP   = 3

    def __init__(self, param_defs: list, parent=None):
        super().__init__(parent)
        self._defs = param_defs   # [(section, name, default, desc), ...]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Load buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_defaults = QPushButton("Load built-in defaults")
        btn_file     = QPushButton("Load from JSON file…")
        btn_reset    = QPushButton("Reset selected to default")
        btn_defaults.clicked.connect(self.load_defaults)
        btn_file.clicked.connect(self._load_from_file)
        btn_reset.clicked.connect(self._reset_selected)
        btn_reset.setToolTip("Reset the currently selected parameter to its built-in default value.")
        btn_row.addWidget(btn_defaults)
        btn_row.addWidget(btn_file)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        self._sweep_label = QLabel("")
        self._sweep_label.setStyleSheet("color: #2266aa; font-style: italic;")
        btn_row.addWidget(self._sweep_label)
        layout.addLayout(btn_row)

        # ── Table ─────────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Section", "Parameter", "Value", "Sweep"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_SECTION, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NAME,    QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_VALUE,   QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_SWEEP,   QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_SWEEP, 55)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked |
                                    QAbstractItemView.SelectedClicked |
                                    QAbstractItemView.EditKeyPressed)
        self.table.currentItemChanged.connect(lambda cur, _: self._show_description(self.table.currentRow()))
        self.table.itemChanged.connect(self._on_item_changed)
        splitter.addWidget(self.table)

        # ── Description pane ──────────────────────────────────────────────────
        self.desc_browser = QTextBrowser()
        self.desc_browser.setMaximumHeight(100)
        self.desc_browser.setPlaceholderText("Click a row to see the parameter description.")
        splitter.addWidget(self.desc_browser)
        splitter.setSizes([400, 100])
        layout.addWidget(splitter)

        # ── Comments ──────────────────────────────────────────────────────────
        comments_row = QHBoxLayout()
        comments_row.addWidget(QLabel("Comments:"))
        self.comments_edit = QLineEdit()
        self.comments_edit.setPlaceholderText(
            "Optional notes (ignored by batch2p and extractors)"
        )
        comments_row.addWidget(self.comments_edit)
        layout.addLayout(comments_row)

        self.load_defaults()

    # ── public API ────────────────────────────────────────────────────────────

    def load_defaults(self):
        self._populate([(s, n, v, d) for s, n, v, d in self._defs])

    def get_params(self) -> tuple[dict, list[tuple]]:
        """Return (base_params_dict, sweep_list).

        base_params_dict: nested dict ready to write as params.json.
        sweep_list: [(section, name, [val1, val2, ...]), ...] for params with Sweep checked.
        """
        base: dict = {}
        sweep_list = []
        n_rows = self.table.rowCount()
        for row in range(n_rows):
            section_item = self.table.item(row, self.COL_SECTION)
            name_item    = self.table.item(row, self.COL_NAME)
            value_item   = self.table.item(row, self.COL_VALUE)
            sweep_cb     = self._get_sweep_cb(row)
            if not (section_item and name_item and value_item):
                continue
            section = section_item.text().strip()
            name    = name_item.text().strip()
            val_str = value_item.text().strip()

            try:
                value = safe_eval(val_str)
            except Exception:
                value = val_str  # keep as string if unparseable

            is_sweep = sweep_cb.isChecked() if sweep_cb else False

            if is_sweep:
                vals = list(value) if hasattr(value, "__iter__") and not isinstance(value, str) else [value]
                sweep_list.append((section, name, vals))
            else:
                if section == "—":
                    base[name] = value
                else:
                    base.setdefault(section, {})[name] = value
        return base, sweep_list

    def get_visible_count(self) -> int:
        """Number of non-sweep parameters (for display)."""
        _, sweeps = self.get_params()
        count = 1
        for _, _, vals in sweeps:
            count *= len(vals)
        return count

    # ── internals ─────────────────────────────────────────────────────────────

    def _populate(self, rows: list):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for r, (section, name, default, desc) in enumerate(rows):
            sec_label = section if section else "—"

            sec_item = QTableWidgetItem(sec_label)
            sec_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            sec_item.setBackground(_SECTION_COLOR)
            sec_item.setFont(bold)
            sec_item.setData(Qt.UserRole, desc)
            self.table.setItem(r, self.COL_SECTION, sec_item)

            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setData(Qt.UserRole, desc)
            self.table.setItem(r, self.COL_NAME, name_item)

            val_item = QTableWidgetItem(value_to_str(default))
            val_item.setData(Qt.UserRole, desc)
            self.table.setItem(r, self.COL_VALUE, val_item)

            sweep_widget = QWidget()
            sweep_layout = QHBoxLayout(sweep_widget)
            sweep_layout.setContentsMargins(4, 0, 4, 0)
            sweep_layout.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.stateChanged.connect(lambda _, row=r: self._on_sweep_toggled(row))
            sweep_layout.addWidget(cb)
            self.table.setCellWidget(r, self.COL_SWEEP, sweep_widget)

        self.table.blockSignals(False)
        self._update_sweep_label()

    def _get_sweep_cb(self, row: int) -> QCheckBox | None:
        widget = self.table.cellWidget(row, self.COL_SWEEP)
        if widget is None:
            return None
        return widget.findChild(QCheckBox)

    def _on_sweep_toggled(self, row: int):
        cb = self._get_sweep_cb(row)
        value_item = self.table.item(row, self.COL_VALUE)
        if value_item:
            if cb and cb.isChecked():
                value_item.setBackground(_SWEEP_COLOR)
                value_item.setToolTip("Enter a Python/numpy list expression, e.g. [0.1, 0.5, 1.0] or np.arange(5)")
            else:
                value_item.setBackground(QColor("white"))
                value_item.setToolTip("")
        self._update_sweep_label()
        self.sweep_changed.emit()

    def _on_item_changed(self, item):
        if item.column() == self.COL_VALUE:
            row = item.row()
            cb = self._get_sweep_cb(row)
            if cb and cb.isChecked():
                item.setBackground(_SWEEP_COLOR)
            self._update_sweep_label()

    def _update_sweep_label(self):
        _, sweeps = self.get_params()
        if not sweeps:
            self._sweep_label.setText("")
            return
        parts = [f"{n}: {len(v)}" for _, n, v in sweeps]
        total = self.get_visible_count()
        self._sweep_label.setText(f"Sweep: {' × '.join(parts)} = {total} configs")

    def _show_description(self, row: int):
        if row < 0:
            return
        item = self.table.item(row, self.COL_NAME)
        if item:
            desc = item.data(Qt.UserRole) or ""
            name = item.text()
            sec_item = self.table.item(row, self.COL_SECTION)
            sec  = sec_item.text() if sec_item else ""
            html = f"<b>{sec + '.' if sec and sec != '—' else ''}{name}</b><br>{desc}"
            self.desc_browser.setHtml(html)

    def _load_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load parameters JSON",
                                               "", "JSON (*.json)")
        if not path:
            return
        with open(path) as f:
            data = json.load(f)
        if "comments" in data:
            self.comments_edit.setText(str(data["comments"]))
        # Flatten two-level dict → {(section, name): value}
        flat: dict[tuple, object] = {}
        for k, v in data.items():
            if k == "comments":
                continue
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat[(k, sub_k)] = sub_v
            else:
                flat[(None, k)] = v
        # Update matching table rows
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            sec_item  = self.table.item(row, self.COL_SECTION)
            name_item = self.table.item(row, self.COL_NAME)
            if not (sec_item and name_item):
                continue
            sec  = sec_item.text()
            name = name_item.text()
            sec_key = None if sec == "—" else sec
            val = flat.get((sec_key, name))
            if val is None:
                # Try flat lookup (top-level overrides)
                val = flat.get((None, name))
            if val is not None:
                self.table.item(row, self.COL_VALUE).setText(value_to_str(val))
        self.table.blockSignals(False)
        self._update_sweep_label()

    def _reset_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        si = self.table.item(row, self.COL_SECTION)
        ni = self.table.item(row, self.COL_NAME)
        if not (si and ni):
            return
        sec  = si.text()
        name = ni.text()
        # Look up default in _defs: match on section label and name
        sec_key = None if sec == "—" else sec
        for def_sec, def_name, def_val, _ in self._defs:
            def_sec_label = def_sec if def_sec else "—"
            if def_sec_label == sec and def_name == name:
                vi = self.table.item(row, self.COL_VALUE)
                if vi:
                    vi.setText(value_to_str(def_val))
                    cb = self._get_sweep_cb(row)
                    if cb and cb.isChecked():
                        vi.setBackground(_SWEEP_COLOR)
                    else:
                        vi.setBackground(QColor("white"))
                return


# ─── RunConfigWidget ──────────────────────────────────────────────────────────

class RunConfigWidget(QWidget):
    """data.json run-configuration fields."""

    algorithm_changed = pyqtSignal(str)
    data_json_imported = pyqtSignal(dict)  # emitted with the full loaded dict

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── Algorithm ─────────────────────────────────────────────────────────
        algo_box = QGroupBox("Source Extraction Algorithm")
        algo_layout = QHBoxLayout(algo_box)
        self._algo_group = QButtonGroup(self)
        self._rb_s2p = QRadioButton("Suite2P")
        self._rb_s3d = QRadioButton("Suite3D")
        self._rb_s2p.setChecked(True)
        self._algo_group.addButton(self._rb_s2p)
        self._algo_group.addButton(self._rb_s3d)
        algo_layout.addWidget(self._rb_s2p)
        algo_layout.addWidget(self._rb_s3d)
        algo_layout.addStretch()
        btn_import = QPushButton("Load from data.json…")
        btn_import.setToolTip("Import run configuration (and optionally file list) from an existing data.json file.")
        btn_import.clicked.connect(self._import_data_json)
        algo_layout.addWidget(btn_import)
        layout.addWidget(algo_box)
        self._rb_s2p.toggled.connect(self._on_algo_changed)
        self._rb_s3d.toggled.connect(self._on_algo_changed)

        # ── Output directory for generated JSON files ─────────────────────────
        out_box = QGroupBox("Output Directory for Generated JSON Files")
        out_layout = QHBoxLayout(out_box)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Directory where data_*.json and params_*.json will be written")
        btn_out = QPushButton("Browse…")
        btn_out.setFixedWidth(80)
        btn_out.clicked.connect(lambda: self._browse_dir(self.output_dir_edit))
        out_layout.addWidget(self.output_dir_edit)
        out_layout.addWidget(btn_out)
        layout.addWidget(out_box)

        # ── SLURM script generation ───────────────────────────────────────────
        slurm_box = QGroupBox("SLURM Job Scripts")
        slurm_layout = QHBoxLayout(slurm_box)
        self._slurm_cb = QCheckBox("Generate .sh scripts from Jinja2 template")
        self._slurm_cb.setToolTip(
            "After generating JSON files, render one SLURM shell script per data.json.\n"
            "Available template variables: {{ data_file }}, {{ job_id }}, {{ params_file }}."
        )
        self._slurm_template_edit = QLineEdit()
        self._slurm_template_edit.setPlaceholderText("Path to Jinja2 .sh.in template file")
        self._slurm_template_edit.setEnabled(False)
        btn_tmpl = QPushButton("Browse…")
        btn_tmpl.setFixedWidth(70)
        btn_tmpl.setEnabled(False)
        btn_tmpl.clicked.connect(self._browse_slurm_template)
        self._slurm_cb.toggled.connect(self._slurm_template_edit.setEnabled)
        self._slurm_cb.toggled.connect(btn_tmpl.setEnabled)
        slurm_layout.addWidget(self._slurm_cb)
        slurm_layout.addWidget(self._slurm_template_edit, stretch=1)
        slurm_layout.addWidget(btn_tmpl)
        layout.addWidget(slurm_box)

        # ── Run-config form ───────────────────────────────────────────────────
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_container = QWidget()
        self._form = QFormLayout(form_container)
        self._form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form_scroll.setWidget(form_container)
        layout.addWidget(form_scroll)

        # Build widgets for each field
        self._widgets: dict[str, QWidget] = {}
        self._rows: dict[str, int] = {}      # field key → form row index
        self._shown_for: dict[str, str] = {} # field key → "both"/"suite2p"/"suite3d"

        for key, label, default, wtype, tooltip, shown_for in DATA_FIELDS:
            self._shown_for[key] = shown_for
            if wtype == "bool":
                w = QCheckBox()
                w.setChecked(bool(default))
            elif wtype == "int":
                w = QLineEdit(str(default))
                w.setFixedWidth(120)
            elif wtype == "path":
                w = self._make_path_row(tooltip)
            elif wtype == "file":
                w = self._make_file_row(tooltip)
            elif wtype == "textarea":
                w = QPlainTextEdit()
                w.setPlaceholderText("Optional notes (ignored by batch2p and extractors)")
                w.setFixedHeight(72)
            else:  # text
                w = QLineEdit(str(default) if default else "")
            if wtype not in ("path", "file"):
                w.setToolTip(tooltip)
            row_label = QLabel(label + ":")
            row_label.setToolTip(tooltip)
            self._form.addRow(row_label, w)
            self._widgets[key] = w
            self._rows[key] = self._form.rowCount() - 1

        self._update_visibility()

    # ── public API ────────────────────────────────────────────────────────────

    def algorithm(self) -> str:
        return "suite2p" if self._rb_s2p.isChecked() else "suite3d"

    def output_dir(self) -> str:
        return self.output_dir_edit.text().strip()

    def get_fields(self) -> dict:
        """Return a dict of data.json run-config fields (non-empty values only)."""
        result = {}
        for key, _, _, wtype, _, shown_for in DATA_FIELDS:
            if shown_for not in ("both", self.algorithm()):
                continue
            w = self._widgets[key]
            if wtype == "bool":
                result[key] = w.isChecked()
            elif wtype in ("path", "file"):
                edit = w.findChild(QLineEdit)
                val = edit.text().strip() if edit else ""
                if val:
                    result[key] = val
            elif wtype == "textarea":
                val = w.toPlainText().strip()
                if val:
                    result[key] = val
            else:
                val = w.text().strip()
                if val:
                    result[key] = int(val) if wtype == "int" and val.lstrip("-").isdigit() else val
        return result

    def slurm_config(self) -> dict | None:
        """Return {'template': path} if SLURM generation is enabled, else None."""
        if not self._slurm_cb.isChecked():
            return None
        tmpl = self._slurm_template_edit.text().strip()
        return {"template": tmpl} if tmpl else None

    def to_dict(self) -> dict:
        return {"algorithm": self.algorithm(),
                "output_dir": self.output_dir(),
                "fields": self.get_fields(),
                "slurm": {"enabled": self._slurm_cb.isChecked(),
                           "template": self._slurm_template_edit.text().strip()}}

    def from_dict(self, d: dict):
        algo = d.get("algorithm", "suite2p")
        (self._rb_s2p if algo == "suite2p" else self._rb_s3d).setChecked(True)
        self.output_dir_edit.setText(d.get("output_dir", ""))
        slurm = d.get("slurm", {})
        self._slurm_cb.setChecked(bool(slurm.get("enabled", False)))
        self._slurm_template_edit.setText(slurm.get("template", ""))
        fields = d.get("fields", {})
        for key, _, _, wtype, _, _ in DATA_FIELDS:
            if key not in fields:
                continue
            w = self._widgets[key]
            val = fields[key]
            if wtype == "bool":
                w.setChecked(bool(val))
            elif wtype in ("path", "file"):
                edit = w.findChild(QLineEdit)
                if edit:
                    edit.setText(str(val))
            elif wtype == "textarea":
                w.setPlainText(str(val))
            else:
                w.setText(str(val))

    def apply_data_json(self, data: dict):
        """Populate run-config fields from a raw data.json dict.

        Sets the algorithm from 'source_extraction', then fills every DATA_FIELDS
        key that is present in *data*.  Fields not present in *data* are left
        unchanged.  The keys 'root_path', 'data', 'behavior_data', and
        'params_file' are intentionally skipped here — the caller is responsible
        for updating the InputFilesWidget with those values.
        """
        algo = data.get("source_extraction", "suite2p")
        (self._rb_s2p if algo == "suite2p" else self._rb_s3d).setChecked(True)
        skip = {"source_extraction", "root_path", "data", "behavior_data", "params_file"}
        for key, _, _, wtype, _, _ in DATA_FIELDS:
            if key in skip or key not in data:
                continue
            w = self._widgets[key]
            val = data[key]
            if wtype == "bool":
                w.setChecked(bool(val))
            elif wtype in ("path", "file"):
                edit = w.findChild(QLineEdit)
                if edit:
                    edit.setText(str(val))
            elif wtype == "textarea":
                w.setPlainText(str(val))
            else:
                w.setText(str(val))

    # ── internals ─────────────────────────────────────────────────────────────

    def _browse_slurm_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Jinja2 template", "",
            "Shell templates (*.sh.in *.sh *.j2 *.jinja2);;All files (*)"
        )
        if path:
            self._slurm_template_edit.setText(path)

    def _import_data_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open data.json",
                                               "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", f"Could not read file:\n{exc}")
            return
        self.apply_data_json(data)
        self.data_json_imported.emit(data)

    def _make_path_row(self, tooltip: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setToolTip(tooltip)
        btn = QPushButton("…")
        btn.setFixedWidth(28)
        btn.clicked.connect(lambda: self._browse_dir(edit))
        row.addWidget(edit)
        row.addWidget(btn)
        return container

    def _make_file_row(self, tooltip: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setToolTip(tooltip)
        btn = QPushButton("…")
        btn.setFixedWidth(28)
        btn.clicked.connect(lambda: self._browse_file(edit))
        row.addWidget(edit)
        row.addWidget(btn)
        return container

    def _browse_file(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Select file",
                                              edit.text() or "",
                                              "JSON files (*.json);;All files (*)")
        if path:
            edit.setText(path)

    def _browse_dir(self, target: QLineEdit):
        # target may be a QLineEdit directly or a container with one inside
        if isinstance(target, QLineEdit):
            edit = target
        else:
            edit = target.findChild(QLineEdit)
        if edit is None:
            return
        path = QFileDialog.getExistingDirectory(self, "Select directory",
                                                  edit.text() or "")
        if path:
            edit.setText(path)

    def _on_algo_changed(self):
        self._update_visibility()
        self.algorithm_changed.emit(self.algorithm())

    def _update_visibility(self):
        algo = self.algorithm()
        for key, _, _, _, _, shown_for in DATA_FIELDS:
            visible = shown_for == "both" or shown_for == algo
            row_idx = self._rows[key]
            label_item = self._form.itemAt(row_idx, QFormLayout.LabelRole)
            field_item = self._form.itemAt(row_idx, QFormLayout.FieldRole)
            for item in (label_item, field_item):
                if item and item.widget():
                    item.widget().setVisible(visible)


# ─── MainWindow ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("batch2p GUI")
        self.resize(1300, 800)

        # ── Menu ──────────────────────────────────────────────────────────────
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        act_new   = QAction("&New project",  self, shortcut="Ctrl+N")
        act_open  = QAction("&Open project…",self, shortcut="Ctrl+O")
        act_save  = QAction("&Save project…",self, shortcut="Ctrl+S")
        act_gen   = QAction("&Generate JSON files…", self, shortcut="Ctrl+G")
        file_menu.addAction(act_new)
        file_menu.addAction(act_open)
        file_menu.addAction(act_save)
        act_exit  = QAction("E&xit", self, shortcut="Ctrl+Q")
        file_menu.addSeparator()
        file_menu.addAction(act_gen)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)
        act_new.triggered.connect(self._new_project)
        act_open.triggered.connect(self._open_project)
        act_save.triggered.connect(self._save_project)
        act_gen.triggered.connect(self._generate)
        act_exit.triggered.connect(self.close)

        # ── Toolbar ───────────────────────────────────────────────────────────
        tb = QToolBar("Main toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(act_new)
        tb.addAction(act_open)
        tb.addAction(act_save)
        tb.addSeparator()
        btn_gen = QPushButton("  ⚙  Generate JSON files  ")
        btn_gen.setFixedHeight(32)
        btn_gen.setStyleSheet("font-weight: bold; background: #2266aa; color: white; border-radius: 4px;")
        btn_gen.clicked.connect(self._generate)
        tb.addWidget(btn_gen)

        # ── Central widget ────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left: input files
        self.input_widget = InputFilesWidget()
        self.input_widget.setMinimumWidth(340)
        splitter.addWidget(self.input_widget)

        # Right: settings tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        self.run_config = RunConfigWidget()
        tabs.addTab(self.run_config, "Run Configuration")

        self.param_table_s2p = ParamTableWidget(S2P_PARAMS)
        self.param_table_s3d = ParamTableWidget(S3D_PARAMS)
        # Stack both in a container; show only the active one
        self._param_stack = QWidget()
        stack_layout = QVBoxLayout(self._param_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self.param_table_s2p)
        stack_layout.addWidget(self.param_table_s3d)
        tabs.addTab(self._param_stack, "Algorithm Parameters")

        right_layout.addWidget(tabs)

        # Status strip
        self._status = QLabel("")
        self._status.setStyleSheet("padding: 4px; background: #f5f5f5;")
        right_layout.addWidget(self._status)

        splitter.addWidget(right_panel)
        splitter.setSizes([420, 880])

        # Connect algorithm change to param table visibility
        self.run_config.algorithm_changed.connect(self._on_algo_changed)
        self._on_algo_changed(self.run_config.algorithm())
        for tbl in (self.param_table_s2p, self.param_table_s3d):
            tbl.sweep_changed.connect(self._update_status)
        self._update_status()
        self.run_config.data_json_imported.connect(self._on_data_json_imported)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    # ── Project save / load ───────────────────────────────────────────────────

    def _new_project(self):
        if QMessageBox.question(self, "New project",
                                 "Discard current project and start fresh?",
                                 QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.input_widget.from_dict({"root_path": "", "tif_files": [], "b64_files": []})
            self.run_config.from_dict({})
            self.param_table_s2p.load_defaults()
            self.param_table_s2p.comments_edit.clear()
            self.param_table_s3d.load_defaults()
            self.param_table_s3d.comments_edit.clear()

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project",
                                               "", "batch2p project (*.b2p.json)")
        if not path:
            return
        if not path.endswith(".b2p.json"):
            path += ".b2p.json"
        project = {
            "input_files": self.input_widget.to_dict(),
            "run_config":  self.run_config.to_dict(),
            "params_s2p":  self._table_to_save(self.param_table_s2p),
            "params_s3d":  self._table_to_save(self.param_table_s3d),
        }
        with open(path, "w") as f:
            json.dump(project, f, indent=2)
        self.statusBar().showMessage(f"Project saved to {path}")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project",
                                               "", "batch2p project (*.b2p.json);;JSON (*.json)")
        if not path:
            return
        with open(path) as f:
            project = json.load(f)
        self.input_widget.from_dict(project.get("input_files", {}))
        self.run_config.from_dict(project.get("run_config", {}))
        self._table_from_save(self.param_table_s2p, project.get("params_s2p", {}))
        self._table_from_save(self.param_table_s3d, project.get("params_s3d", {}))
        self.statusBar().showMessage(f"Project loaded from {path}")

    @staticmethod
    def _table_to_save(table: ParamTableWidget) -> dict:
        """Serialise table state (values + sweep flags) for project files."""
        rows = []
        for r in range(table.table.rowCount()):
            si = table.table.item(r, ParamTableWidget.COL_SECTION)
            ni = table.table.item(r, ParamTableWidget.COL_NAME)
            vi = table.table.item(r, ParamTableWidget.COL_VALUE)
            cb = table._get_sweep_cb(r)
            if si and ni and vi:
                rows.append({
                    "section": si.text(),
                    "name":    ni.text(),
                    "value":   vi.text(),
                    "sweep":   cb.isChecked() if cb else False,
                })
        return {"rows": rows, "comments": table.comments_edit.text()}

    @staticmethod
    def _table_from_save(table: ParamTableWidget, saved: dict):
        rows = saved.get("rows", [])
        lookup = {(r["section"], r["name"]): r for r in rows}
        table.table.blockSignals(True)
        for r in range(table.table.rowCount()):
            si = table.table.item(r, ParamTableWidget.COL_SECTION)
            ni = table.table.item(r, ParamTableWidget.COL_NAME)
            vi = table.table.item(r, ParamTableWidget.COL_VALUE)
            cb = table._get_sweep_cb(r)
            if si and ni and vi:
                key = (si.text(), ni.text())
                saved_row = lookup.get(key)
                if saved_row:
                    vi.setText(saved_row["value"])
                    if cb:
                        cb.setChecked(saved_row.get("sweep", False))
        table.table.blockSignals(False)
        table._update_sweep_label()
        table.comments_edit.setText(saved.get("comments", ""))

    # ── Generate ──────────────────────────────────────────────────────────────

    def _generate(self):
        # Collect data
        algo     = self.run_config.algorithm()
        out_dir  = self.run_config.output_dir()
        fields   = self.run_config.get_fields()
        file_data = self.input_widget.to_dict()
        param_table = self.param_table_s2p if algo == "suite2p" else self.param_table_s3d

        # Validate
        errors = []
        if not out_dir:
            errors.append("Output directory is not set (Run Configuration tab).")
        if not file_data.get("tif_files"):
            errors.append("No TIFF files selected.")
        if not fields.get("job_id"):
            errors.append("Job ID is not set.")

        # Try to evaluate sweep values; collect errors
        # Suite3D params.json must be a flat (single-level) dict; sections are
        # display-only in the GUI and must not appear as nested keys in the file.
        flat_params = (algo == "suite3d")
        base_params, sweep_list = self._validate_sweep(param_table, errors, flat=flat_params)
        if errors:
            QMessageBox.critical(self, "Validation error",
                                  "Please fix the following issues:\n\n" + "\n".join(f"• {e}" for e in errors))
            return

        # Confirm
        n_configs = 1
        for _, _, vals in sweep_list:
            n_configs *= len(vals)
        msg = (f"Algorithm:  {algo}\n"
               f"Job ID:     {fields.get('job_id', '')}\n"
               f"Output dir: {out_dir}\n\n"
               f"This will generate {n_configs} data.json + params.json file pair{'s' if n_configs > 1 else ''}.\n"
               "Proceed?")
        if QMessageBox.question(self, "Generate JSON files", msg,
                                 QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        # Generate
        try:
            out_path = Path(out_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            job_id = fields.get("job_id", "run")

            # Load Jinja2 template once (if requested)
            slurm_cfg = self.run_config.slurm_config()
            jinja_template = None
            if slurm_cfg:
                try:
                    from jinja2 import Environment, FileSystemLoader, StrictUndefined
                    tmpl_path = Path(slurm_cfg["template"])
                    env = Environment(
                        loader=FileSystemLoader(str(tmpl_path.parent)),
                        undefined=StrictUndefined,
                        keep_trailing_newline=True,
                    )
                    jinja_template = env.get_template(tmpl_path.name)
                except ImportError:
                    QMessageBox.critical(self, "Missing dependency",
                                         "jinja2 is required for SLURM script generation.\n"
                                         "Install it with:  pip install jinja2")
                    return
                except Exception as exc:
                    QMessageBox.critical(self, "Template error",
                                         f"Could not load template:\n{exc}")
                    return

            combinations = self._expand_sweeps(sweep_list)
            if not combinations:
                combinations = [{}]

            generated_pairs = []
            digits = len(str(len(combinations)))
            for idx, combo in enumerate(combinations, start=1):
                # Build params dict for this combo
                params_dict = copy.deepcopy(base_params)
                for section, name, val in combo:
                    if flat_params or section == "—" or not section:
                        params_dict[name] = val
                    else:
                        params_dict.setdefault(section, {})[name] = val
                params_comments = param_table.comments_edit.text().strip()
                if params_comments:
                    params_dict["comments"] = params_comments
                params_dict = make_json_serializable(params_dict)

                # File naming
                suffix = f"_{idx:0{digits}d}" if len(combinations) > 1 else ""
                params_fname = f"{job_id}{suffix}_params.json"
                data_fname   = f"{job_id}{suffix}_data.json"
                params_path  = out_path / params_fname
                data_path_f  = out_path / data_fname

                with open(params_path, "w") as f:
                    json.dump(params_dict, f, indent=2)

                # Build data.json — prepend root_path to make entries absolute server paths
                root_path = file_data.get("root_path", "")
                tif_rel = file_data.get("tif_files", [])
                b64_rel = file_data.get("b64_files", [])
                if root_path:
                    root = Path(root_path)
                    tif_entries = [str(root / p) for p in tif_rel]
                    b64_entries = [str(root / p) for p in b64_rel]
                else:
                    tif_entries = tif_rel
                    b64_entries = b64_rel

                data_dict = {
                    "source_extraction": algo,
                    "params_file": str(params_path.resolve()),
                    "data": tif_entries,
                }
                if root_path:
                    data_dict["root_path"] = root_path
                if b64_entries:
                    data_dict["behavior_data"] = b64_entries
                data_dict.update(fields)
                # Give each sweep configuration a unique job_id by appending the
                # same numeric suffix used in the file names.
                if suffix:
                    data_dict["job_id"] = f"{job_id}{suffix}"
                data_dict = make_json_serializable(data_dict)
                data_dict = _apply_template_vars(data_dict, {
                    "job_id":   data_dict.get("job_id", ""),
                    "root_dir": root_path,
                })

                with open(data_path_f, "w") as f:
                    json.dump(data_dict, f, indent=2)

                generated_pairs.append((params_fname, data_fname))

            # One SLURM script covers all configurations (array or single).
            sh_fname = None
            if jinja_template is not None:
                is_array = len(combinations) > 1
                sh_fname = f"{job_id}.sh"
                # For the non-array case supply the exact data file path.
                single_data_file = str((out_path / f"{job_id}_data.json").resolve())
                rendered = jinja_template.render(
                    is_array=is_array,
                    n_jobs=len(combinations),
                    index_digits=digits,
                    out_dir=str(out_path.resolve()),
                    job_id=job_id,
                    data_file=single_data_file,
                    working_dir=fields.get("working_dir", ""),
                )
                with open(out_path / sh_fname, "w") as f:
                    f.write(rendered)

            # Summary
            lines = [f"Generated {len(generated_pairs)} configuration(s) in:\n{out_dir}\n"]
            for pf, df in generated_pairs[:10]:
                lines.append(f"  {df}  +  {pf}")
            if len(generated_pairs) > 10:
                lines.append(f"  … and {len(generated_pairs) - 10} more")
            if sh_fname:
                array_note = f" (job array 1–{len(combinations)})" if len(combinations) > 1 else ""
                lines.append(f"\nSLURM script{array_note}:  {sh_fname}")
            QMessageBox.information(self, "Generation complete", "\n".join(lines))
            what = "config pair(s)" + (f" + {sh_fname}" if sh_fname else "")
            self.statusBar().showMessage(f"Generated {len(generated_pairs)} {what} → {out_dir}")

        except Exception as exc:
            QMessageBox.critical(self, "Generation failed", str(exc))

    @staticmethod
    def _validate_sweep(table: ParamTableWidget, errors: list,
                        flat: bool = False) -> tuple[dict, list]:
        """Evaluate and validate sweep parameters. Appends to errors on failure.

        When *flat* is True every parameter is written as a top-level key
        regardless of its section (required for Suite3D params.json).
        """
        base_params: dict = {}
        sweep_list = []
        for row in range(table.table.rowCount()):
            si = table.table.item(row, ParamTableWidget.COL_SECTION)
            ni = table.table.item(row, ParamTableWidget.COL_NAME)
            vi = table.table.item(row, ParamTableWidget.COL_VALUE)
            cb = table._get_sweep_cb(row)
            if not (si and ni and vi):
                continue
            section  = si.text().strip()
            name     = ni.text().strip()
            val_str  = vi.text().strip()
            is_sweep = cb.isChecked() if cb else False

            try:
                value = safe_eval(val_str)
            except Exception as e:
                errors.append(f"Parameter '{name}' — invalid expression '{val_str}': {e}")
                continue

            if is_sweep:
                if not hasattr(value, "__iter__") or isinstance(value, str):
                    errors.append(f"Parameter '{name}' is marked Sweep but value is not a list/array.")
                    continue
                vals = list(value)
                if not vals:
                    errors.append(f"Parameter '{name}' sweep list is empty.")
                    continue
                sweep_list.append((section, name, vals))
            else:
                if flat or section == "—" or not section:
                    base_params[name] = value
                else:
                    base_params.setdefault(section, {})[name] = value

        return base_params, sweep_list

    @staticmethod
    def _expand_sweeps(sweep_list: list) -> list[list[tuple]]:
        """Return a list of combinations; each combination is a list of (section, name, value)."""
        if not sweep_list:
            return []
        keys   = [(s, n) for s, n, _ in sweep_list]
        values = [v for _, _, v in sweep_list]
        combos = []
        for combo_vals in itertools.product(*values):
            combos.append([(sec, name, val)
                           for (sec, name), val in zip(keys, combo_vals)])
        return combos

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _on_data_json_imported(self, data: dict):
        """Offer to also import root_path / data / behavior_data into the file list."""
        has_files = bool(data.get("data") or data.get("behavior_data") or data.get("root_path"))
        if not has_files:
            return
        reply = QMessageBox.question(
            self, "Import file list",
            "The data.json also contains file-list entries (root_path / data / behavior_data).\n"
            "Import them into the Input Files panel as well?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        root = data.get("root_path", "")
        tif_entries = data.get("data", [])
        b64_entries = data.get("behavior_data", [])
        # Strip root_path prefix so the file list shows relative paths.
        def to_rel(entries, root_dir):
            if not root_dir:
                return entries
            r = Path(root_dir)
            result = []
            for e in entries:
                try:
                    result.append(str(Path(e).relative_to(r)))
                except ValueError:
                    result.append(e)
            return result
        self.input_widget.from_dict({
            "root_path": root,
            "tif_files": to_rel(tif_entries, root),
            "b64_files": to_rel(b64_entries, root),
        })

    def _on_algo_changed(self, algo: str):
        is_s2p = algo == "suite2p"
        self.param_table_s2p.setVisible(is_s2p)
        self.param_table_s3d.setVisible(not is_s2p)
        self._update_status()

    def _update_status(self):
        algo = self.run_config.algorithm()
        tbl  = self.param_table_s2p if algo == "suite2p" else self.param_table_s3d
        n    = tbl.get_visible_count()
        self._status.setText(
            f"Algorithm: <b>{algo}</b>   |   "
            f"{'<b>' + str(n) + ' run configuration(s)</b> will be generated' if n > 1 else '1 run configuration will be generated'}"
        )


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("batch2p GUI")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
