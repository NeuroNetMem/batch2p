from .base import SourceExtractor
from .suite3d import Suite3DExtractor
from .suite2p import Suite2PExtractor

_EXTRACTORS = {
    "suite3d": Suite3DExtractor,
    "suite2p": Suite2PExtractor,
}


def get_extractor(name: str, data: dict) -> SourceExtractor:
    if name not in _EXTRACTORS:
        raise ValueError(
            f"Unknown source_extraction algorithm: {name!r}. "
            f"Supported: {list(_EXTRACTORS)}"
        )
    return _EXTRACTORS[name](data)
