"""Setup script for ofl_2p_analysis project."""

from setuptools import setup, find_packages

setup(
    name='ofl_2p_analysis',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'scipy',
        'cobs',
        'tqdm',
        'matplotlib',
        'pandas',
        'pynapple',
        'seaborn',
		'ipympl'
    ],
    entry_points={
        'console_scripts': [
            'totalsync-decode=totalsync_utils.cli:main',
            'batch2p=batch2p.cli:main',
            'batch2p-gui=batch2p.gui:main',
            'batch2p-multi=batch2p.multi:main',
            'totalsync-2p-sync=totalsync_2p.cli:main',
        ],
    },
    python_requires='>=3.7',
)
