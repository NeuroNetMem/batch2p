"""Abstract base class for source extraction algorithms."""
from abc import ABC, abstractmethod
from pathlib import Path


class SourceExtractor(ABC):
    """Abstract base class for 2-photon source extraction algorithms."""

    def __init__(self, data: dict):
        self.data = data

    @abstractmethod
    def run(self, tifs: list[Path], job_root_dir: Path, job_id: str, results_path: Path) -> None:
        """Run source extraction on the given TIF files."""

    @abstractmethod
    def get_job_subdir(self, job_id: str) -> str:
        """Return the name of the subdirectory created under job_root_dir by this algorithm."""

    @abstractmethod
    def create_synced_outputs(
        self,
        tif_files: list[Path],
        sync_results: list[dict],
        results_path: Path,
        behavior_sync_dir: Path,
        block_size: int,
    ) -> None:
        """Create behavior-synchronized outputs from extraction results."""

    def save_reproducibility_info(self, results_path: Path) -> None:
        """Optionally save algorithm-specific config files to results_path."""
