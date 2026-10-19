# batch2p

Batch 2-photon preprocessing pipeline. Runs configurable source extraction (suite2p or suite3d) from a single JSON configuration file.


This package streamlines source extraction from tiff files (at the moment ScanImage files are supported). [Suite2p](https://suite2p.readthedocs.io/en/latest/) and [Suite3d](https://github.com/alihaydaroglu/suite3d/)
are currently supported, with features like: 
- file concatenation 
- flexible parameters handling (also including parameter "sweeps")
- creation of batch files for SLURM
- if the experiment used [totalsync](https://github.com/NeuroNetMem/totalsync) for synchronization, imaging and other experimental data (eg. behavioral) are automatically synchronized.
## Installation

The recommended way to install batch2p is with [uv](https://docs.astral.sh/uv/). If you don't have it yet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Custom uv cache location (e.g. home directory quota issues)

By default uv stores its cache in `~/.cache/uv` (Linux) or `~/Library/Caches/uv` (macOS). The dependencies of batch2p (torch, suite2p, ...) are large, so on systems with a small home-directory quota you should point uv to a different location, **before** installing anything:

```bash
export UV_CACHE_DIR=/path/to/large/disk/uv-cache
```

Add this line to your `~/.bashrc` (or `~/.zshrc`) to make it permanent. Alternatively, pass it per command with `uv --cache-dir /path/to/large/disk/uv-cache ...`, or set `cache-dir = "/path/to/large/disk/uv-cache"` in `~/.config/uv/uv.toml`.

Other uv data can also fill up your home directory; you can relocate it in the same way:

```bash
export UV_TOOL_DIR=/path/to/large/disk/uv-tools            # environments created by `uv tool install`
export UV_PYTHON_INSTALL_DIR=/path/to/large/disk/uv-python # Python interpreters downloaded by uv
```

If the cache and the target environment are on different filesystems, uv cannot hard-link packages and will fall back to copying them, which may produce a warning. Setting `UV_LINK_MODE=copy` silences it.

### As a command-line tool (using uv)

```bash
uv tool install batch2p
```

This makes the `batch2p`, `batch2p-multi`, `batch2p-gui` and `batch2p-compute-fsub` commands available on your `PATH`.

### In a uv project

```bash
uv add batch2p
```

or, in an existing virtual environment:

```bash
uv pip install batch2p
```

### From source (using uv)

```bash
git clone https://github.com/NeuroNetMem/batch2p.git
cd batch2p
uv sync              # creates .venv and installs batch2p with the locked dependencies
uv run batch2p --help
```

To install the optional GUI dependencies explicitly, use `uv sync --extra gui` (or `uv pip install ".[gui]"`).

### Using pip

```bash
pip install batch2p
```

or from a source checkout:

```bash
git clone https://github.com/NeuroNetMem/batch2p.git
cd batch2p
pip install .         # or: pip install ".[gui]"
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
