import shutil
import sys
from pathlib import Path

from pdfc.errors import MissingDependency

# How each family installs things.
_COMMANDS: dict[str, str] = {
    "arch": "sudo pacman -S {}",
    "debian": "sudo apt install {}",
    "fedora": "sudo dnf install {}",
    "suse": "sudo zypper install {}",
    "brew": "brew install {}",
}

# The same tool is packaged under different names on different systems.
_PACKAGES: dict[str, dict[str, str]] = {
    "libreoffice": {
        "arch": "libreoffice-fresh",
        "debian": "libreoffice",
        "fedora": "libreoffice",
        "suse": "libreoffice",
        "brew": "--cask libreoffice",
    },
    "tesseract": {
        "arch": "tesseract tesseract-data-eng",
        "debian": "tesseract-ocr",
        "fedora": "tesseract",
        "suse": "tesseract-ocr",
        "brew": "tesseract",
    },
    "gs": {
        "arch": "ghostscript",
        "debian": "ghostscript",
        "fedora": "ghostscript",
        "suse": "ghostscript",
        "brew": "ghostscript",
    },
    "ocrmypdf": {
        "debian": "ocrmypdf",
        "fedora": "ocrmypdf",
        "suse": "ocrmypdf",
        "brew": "ocrmypdf",
    },
    # weasyprint loads these at import time, so they are reported by name.
    "pango": {
        "arch": "pango cairo",
        "debian": "libpango-1.0-0 libcairo2",
        "fedora": "pango cairo",
        "suse": "pango cairo",
        "brew": "pango cairo",
    },
}

# Where a family's usual command is not the right one.
_OVERRIDES: dict[tuple[str, str], str] = {
    ("ocrmypdf", "arch"): "paru -S ocrmypdf   (ocrmypdf is in the AUR)",
}

# tesseract's per-language training data, which every family names differently.
_LANGUAGE_PACKS: dict[str, str] = {
    "arch": "tesseract-data-{language}",
    "debian": "tesseract-ocr-{language}",
    "fedora": "tesseract-langpack-{language}",
    "suse": "tesseract-ocr-traineddata-{language}",
    "brew": "tesseract-lang",
}

# os-release identifiers, and what they are compatible with, mapped to a family.
_FAMILY_BY_ID: dict[str, str] = {
    "arch": "arch",
    "archarm": "arch",
    "manjaro": "arch",
    "endeavouros": "arch",
    "cachyos": "arch",
    "debian": "debian",
    "ubuntu": "debian",
    "linuxmint": "debian",
    "pop": "debian",
    "raspbian": "debian",
    "fedora": "fedora",
    "rhel": "fedora",
    "centos": "fedora",
    "rocky": "fedora",
    "almalinux": "fedora",
    "opensuse": "suse",
    "opensuse-leap": "suse",
    "opensuse-tumbleweed": "suse",
    "sles": "suse",
    "suse": "suse",
}

_UNSET = object()

_cache: dict[str, str | None] = {}
_family: str | None | object = _UNSET  # None means "recognised as nothing we know"


def _read_os_release_ids(path: Path = Path("/etc/os-release")) -> list[str]:
    """The system's own id first, then the ones it says it is compatible with."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    own: list[str] = []
    like: list[str] = []
    for line in text.splitlines():
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'").lower()
        if key == "ID" and value:
            own.append(value)
        elif key == "ID_LIKE" and value:
            like.extend(value.split())
    return own + like


def detect_family() -> str | None:
    """Which packaging family this machine belongs to, or None if unrecognised."""
    global _family
    if _family is not _UNSET:
        return _family  # type: ignore[return-value]
    if sys.platform == "darwin":
        _family = "brew"
    else:
        _family = None
        for identifier in _read_os_release_ids():
            if identifier in _FAMILY_BY_ID:
                _family = _FAMILY_BY_ID[identifier]
                break
    return _family  # type: ignore[return-value]


def install_hint(binary: str) -> str:
    """The command this machine's user should actually run to get `binary`."""
    family = detect_family()
    if family is None:
        return f"install {binary}"
    override = _OVERRIDES.get((binary, family))
    if override:
        return override
    package = _PACKAGES.get(binary, {}).get(family)
    if package is None:
        return f"install {binary}"
    return _COMMANDS[family].format(package)


def language_pack_hint(language: str) -> str:
    """The command for tesseract's training data for one language."""
    family = detect_family()
    if family is None:
        return f"install the tesseract training data for {language}"
    return _COMMANDS[family].format(_LANGUAGE_PACKS[family].format(language=language))


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
    global _family
    _cache.clear()
    _family = _UNSET
