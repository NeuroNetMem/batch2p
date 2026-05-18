from .base import SourceExtractor
from .suite3d import Suite3DExtractor

_EXTRACTORS = {
    "suite3d": Suite3DExtractor,
}


def get_extractor(name: str, data: dict) -> SourceExtractor:
    if name not in _EXTRACTORS:
        raise ValueError(
            f"Unknown source_extraction algorithm: {name!r}. "
            f"Supported: {list(_EXTRACTORS)}"
        )
    return _EXTRACTORS[name](data)
