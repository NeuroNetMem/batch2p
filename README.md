# batch2p

Batch 2-photon preprocessing pipeline. Runs configurable source extraction (suite2p or suite3d) from a single JSON configuration file.


This package streamlines source extraction from tiff files (at the moment ScanImage files are supported). [Suite2p](https://suite2p.readthedocs.io/en/latest/) and [Suite3d](https://github.com/alihaydaroglu/suite3d/)
are currently supported, with features like: 
- file concatenation 
- flexible parameters handling (also including parameter "sweeps")
- creation of batch files for SLURM
- if the experiment used [totalsync](https://github.com/NeuroNetMem/totalsync) for synchronization, imaging and other experimental data (eg. behavioral) are automatically synchronized.
## Installation

### From PyPI

```bash
pip install batch2p
```

### From source (using pip)

```bash
git clone https://github.com/NeuroNetMem/batch2p.git
cd batch2p
pip install . # (or uv pip install ".[all]" )
```

this will install batch2p without GUI support, (which is suitable for headless servers). To install the GUI, replace the last line with
```bash
pip install ".[gui]" # (or uv pip install ".[gui]" )
```

### From source (using uv)

```bash
git clone https://github.com/NeuroNetMem/batch2p.git
cd batch2p
uv pip install .
```

### suite3d (optional)

If you need suite3d support, install it manually from source **after** installing batch2p. See instructions at https://github.com/alihaydaroglu/suite3d. 

Briefly, 

- Clone the suite3d repository (in a different directory):

```bash
git clone https://github.com/alihaydaroglu/suite3d.git
```

```bash
cd suite3d 
pip install ".[all]" # (or uv pip install ".[all]" )
```

Then, install the suite3d cuda dependencies:

```bash
pip install "cupy-cuda13x" # for CUDA 13.X, for other CUDA versions change accordingly
```



## Usage

Detailed usage documentation can be found in the [docs](docs) directory.

- [batch2p](docs/batch2p.md) — single-session pipeline
- [batch2p-multi](docs/batch2p_multi.md) — multi-session batch runner
- [batch2p-gui](docs/batch2p_gui.md) — graphical interface
