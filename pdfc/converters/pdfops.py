import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from pdfc import deps
from pdfc.errors import BadInput
from pdfc.pages import parse_pages
from pdfc.planning import check_writable, output_paths
from pdfc.progress import Reporter

QUALITIES = ("screen", "ebook", "printer", "prepress")
ANGLES = (90, 180, 270, -90)


def _require_pdf(path: Path) -> None:
    if not path.exists():
        raise BadInput(f"cannot read {path}")
    with path.open("rb") as handle:
        header = handle.read(4)
    if header != b"%PDF":
        raise BadInput(f"{path} is not a PDF")


def _validate_gs_output(staged: Path) -> None:
    """Ghostscript can exit 0 while writing an empty or truncated file (e.g. on
    malformed or encrypted input). Confirm the result is actually a readable PDF
    before treating it as a candidate to move into place."""
    if not staged.exists() or staged.stat().st_size == 0:
        raise BadInput("ghostscript produced an empty output file")
    _require_pdf(staged)
    try:
        with pymupdf.open(staged) as doc:
            if doc.page_count < 1:
                raise BadInput("ghostscript produced a PDF with no pages")
    except BadInput:
        raise
    except Exception as error:
        raise BadInput(f"ghostscript produced an unreadable PDF: {error}") from error


def _size(byte_count: int) -> str:
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def merge(sources: list[Path], target: Path, reporter: Reporter, force: bool) -> list[Path]:
    for source in sources:
        _require_pdf(source)
    destination = output_paths(target, sources[0].stem, 1, "pdf")[0]
    check_writable([destination], force)
    reporter.start(("merging", "merged"), f"{len(sources)} files → pdf", len(sources))
    destination.parent.mkdir(parents=True, exist_ok=True)
    out = pymupdf.open()
    for source in sources:
        with pymupdf.open(source) as doc:
            out.insert_pdf(doc)
        reporter.advance()
    out.save(destination)
    out.close()
    reporter.finish(f"{destination}  {_size(destination.stat().st_size)}")
    return [destination]


def split(
    source: Path,
    target: Path,
    pages: str | None,
    every: int | None,
    each: bool,
    reporter: Reporter,
    force: bool,
) -> list[Path]:
    _require_pdf(source)
    modes = [pages is not None, every is not None, each]
    if sum(modes) != 1:
        raise BadInput("pass exactly one of --pages, --every, or --each")

    with pymupdf.open(source) as doc:
        total = doc.page_count
        groups = _split_groups(pages, every, each, total)
        destinations = output_paths(target, source.stem, len(groups), "pdf")
        check_writable(destinations, force)
        reporter.start(("splitting", "split"), f"{source.name} → {len(groups)} files", len(groups))
        for group, destination in zip(groups, destinations, strict=True):
            destination.parent.mkdir(parents=True, exist_ok=True)
            out = pymupdf.open()
            out.insert_pdf(doc, from_page=group[0] - 1, to_page=group[-1] - 1)
            if len(group) != group[-1] - group[0] + 1:
                out.select([page - group[0] for page in group])
            out.save(destination)
            out.close()
            reporter.advance()
    reporter.finish(f"{len(destinations)} files → {destinations[0].parent}")
    return destinations


def _split_groups(pages: str | None, every: int | None, each: bool, total: int) -> list[list[int]]:
    if pages is not None:
        return [parse_pages(pages, total)]
    if each:
        return [[number] for number in range(1, total + 1)]
    if every is not None and every < 1:
        raise BadInput("--every must be at least 1")
    assert every is not None
    return [list(range(start, min(start + every, total + 1))) for start in range(1, total + 1, every)]


def rotate(
    source: Path, target: Path, angle: int, pages: str | None, reporter: Reporter, force: bool
) -> list[Path]:
    _require_pdf(source)
    if angle not in ANGLES:
        raise BadInput(f"angle must be one of {', '.join(str(a) for a in ANGLES)}")
    destination = output_paths(target, source.stem, 1, "pdf")[0]
    check_writable([destination], force)
    with pymupdf.open(source) as doc:
        selected = parse_pages(pages, doc.page_count) if pages else list(range(1, doc.page_count + 1))
        reporter.start(("rotating", "rotated"), f"{source.name}  {angle}°", len(selected))
        for number in selected:
            page = doc[number - 1]
            page.set_rotation((page.rotation + angle) % 360)
            reporter.advance()
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc.save(destination)
    reporter.finish(f"{destination}  {len(selected)} pages")
    return [destination]


def extract_pages(
    source: Path, target: Path, pages: str, reporter: Reporter, force: bool
) -> list[Path]:
    return split(source, target, pages=pages, every=None, each=False, reporter=reporter, force=force)


def compress(
    source: Path, target: Path, quality: str, reporter: Reporter, force: bool
) -> list[Path]:
    _require_pdf(source)
    if quality not in QUALITIES:
        raise BadInput(f"quality must be one of {', '.join(QUALITIES)}")
    binary = deps.require("gs", "compress")
    destination = output_paths(target, source.stem, 1, "pdf")[0]
    check_writable([destination], force)
    before = source.stat().st_size
    reporter.start(("compressing", "compressed"), f"{source.name}  {quality}", None)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pdfc-gs-") as scratch:
        staged = Path(scratch) / "out.pdf"
        subprocess.run(
            [
                binary,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS=/{quality}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={staged}",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        _validate_gs_output(staged)
        after = staged.stat().st_size
        if after >= before:
            shutil.copyfile(source, destination)
            reporter.finish(
                f"{destination}  {_size(before)} → {_size(after)}; kept original (compression made it larger)"
            )
            return [destination]
        shutil.move(str(staged), destination)
    reporter.finish(f"{destination}  {_size(before)} → {_size(after)}")
    return [destination]
