import zipfile
from enum import Enum
from pathlib import Path

from pdfc.errors import BadInput


class Format(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    TIFF = "tiff"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    DOCX = "docx"
    ODT = "odt"
    PPTX = "pptx"
    XLSX = "xlsx"


RASTER = frozenset({Format.PNG, Format.JPEG, Format.WEBP, Format.TIFF})
OFFICE = frozenset({Format.DOCX, Format.ODT, Format.PPTX, Format.XLSX})

EXTENSIONS: dict[str, Format] = {
    ".pdf": Format.PDF,
    ".png": Format.PNG,
    ".jpg": Format.JPEG,
    ".jpeg": Format.JPEG,
    ".webp": Format.WEBP,
    ".tif": Format.TIFF,
    ".tiff": Format.TIFF,
    ".txt": Format.TXT,
    ".md": Format.MD,
    ".markdown": Format.MD,
    ".html": Format.HTML,
    ".htm": Format.HTML,
    ".docx": Format.DOCX,
    ".odt": Format.ODT,
    ".pptx": Format.PPTX,
    ".xlsx": Format.XLSX,
}

ALIASES: dict[str, Format] = {"jpg": Format.JPEG, "tif": Format.TIFF, "markdown": Format.MD, "htm": Format.HTML}

# Marker strings inside the zip container that identify each office format.
_ZIP_MARKERS: list[tuple[str, Format]] = [
    ("wordprocessingml.document", Format.DOCX),
    ("presentationml.presentation", Format.PPTX),
    ("spreadsheetml.sheet", Format.XLSX),
    ("opendocument.text", Format.ODT),
]


def from_name(name: str) -> Format:
    key = name.strip().lower().lstrip(".")
    if key in ALIASES:
        return ALIASES[key]
    try:
        return Format(key)
    except ValueError:
        known = ", ".join(sorted(f.value for f in Format))
        raise BadInput(f"unknown format {name!r}; known formats: {known}") from None


def from_extension(path: Path) -> Format | None:
    return EXTENSIONS.get(path.suffix.lower())


def sniff(path: Path) -> Format | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(12)
    except OSError:
        return None
    if head.startswith(b"%PDF"):
        return Format.PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Format.PNG
    if head.startswith(b"\xff\xd8\xff"):
        return Format.JPEG
    # RIFF is a container: WAV and AVI share the header, so the form type
    # at bytes 8-12 is what actually identifies a WEBP.
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return Format.WEBP
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return Format.TIFF
    if head.startswith(b"PK\x03\x04"):
        return _sniff_zip(path)
    return None


def _sniff_zip(path: Path) -> Format | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            blob = " ".join(names)
            if "mimetype" in names:
                blob += " " + archive.read("mimetype").decode("utf-8", "replace")
            if "[Content_Types].xml" in names:
                blob += " " + archive.read("[Content_Types].xml").decode("utf-8", "replace")
    except (OSError, zipfile.BadZipFile):
        return None
    for marker, fmt in _ZIP_MARKERS:
        if marker in blob:
            return fmt
    return None


def detect_input(path: Path, override: Format | None) -> Format:
    if override is not None:
        return override
    sniffed = sniff(path)
    if sniffed is not None:
        return sniffed
    guessed = from_extension(path)
    if guessed is not None:
        return guessed
    raise BadInput(f"cannot tell what format {path} is; pass --from")


def detect_output(path: Path, override: Format | None) -> Format:
    if override is not None:
        return override
    guessed = from_extension(path)
    if guessed is not None:
        return guessed
    raise BadInput(f"cannot tell what format {path} should be; pass --to")
