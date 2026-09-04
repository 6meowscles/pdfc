import shutil

from pdfc.errors import MissingDependency

HINTS: dict[str, str] = {
    "libreoffice": "sudo pacman -S libreoffice-fresh",
    "tesseract": "sudo pacman -S tesseract tesseract-data-eng",
    "gs": "sudo pacman -S ghostscript",
}

_cache: dict[str, str | None] = {}


def install_hint(binary: str) -> str:
    return HINTS.get(binary, f"install {binary}")


def _resolve(binary: str) -> str | None:
    if binary not in _cache:
        _cache[binary] = shutil.which(binary)
    return _cache[binary]


def have(binary: str) -> bool:
    return _resolve(binary) is not None


def require(binary: str, operation: str) -> str:
    path = _resolve(binary)
    if path is None:
        raise MissingDependency(binary, install_hint(binary), operation)
    return path


def reset_cache() -> None:
    _cache.clear()
