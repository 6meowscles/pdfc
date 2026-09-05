import shutil
import subprocess
from pathlib import Path

import pymupdf

from pdfc import deps
from pdfc.errors import BadInput
from pdfc.pages import parse_pages
from pdfc.planning import check_writable, output_paths, stage_and_move
from pdfc.progress import Reporter, human_size

QUALITIES = ("screen", "ebook", "printer", "prepress")
ANGLES = (90, 180, 270, -90)


def _require_pdf(path: Path) -> None:
    if not path.exists():
        raise BadInput(f"cannot read {path}")
    with path.open("rb") as handle:
        header = handle.read(4)
    if header != b"%PDF":
        raise BadInput(f"{path} is not a PDF")


def _page_count(path: Path) -> int:
    try:
        with pymupdf.open(path) as doc:
            return doc.page_count
    except Exception as error:
        raise BadInput(f"cannot read {path}: {error}") from error


def _validate_gs_output(staged: Path, expected_pages: int) -> None:
    """Ghostscript can exit 0 while writing an empty or truncated file (e.g. on
    malformed or encrypted input). Its subtler failure on a damaged PDF is to
    silently drop pages, leaving a perfectly readable but incomplete result, so
    the page count has to be compared with the source's, not merely be >= 1."""
    if not staged.exists() or staged.stat().st_size == 0:
        raise BadInput("ghostscript produced an empty output file")
    _require_pdf(staged)
    try:
        pages = _page_count(staged)
    except Exception as error:
        raise BadInput(f"ghostscript produced an unreadable PDF: {error}") from error
    if pages < 1:
        raise BadInput("ghostscript produced a PDF with no pages")
    if pages != expected_pages:
        raise BadInput(
            f"ghostscript dropped pages: {expected_pages} in, {pages} out"
        )


def merge(sources: list[Path], target: Path, reporter: Reporter, force: bool) -> list[Path]:
    for source in sources:
        _require_pdf(source)
    destination = output_paths(target, sources[0].stem, 1, "pdf")[0]
    check_writable([destination], force)
    reporter.start(("merging", "merged"), f"{len(sources)} files → pdf", len(sources))

    def write(staged: Path) -> None:
        out = pymupdf.open()
        try:
            for source in sources:
                with pymupdf.open(source) as doc:
                    out.insert_pdf(doc)
                reporter.advance()
            out.save(staged)
        finally:
            out.close()

    stage_and_move(destination, write)
    reporter.finish(f"{destination}  {human_size(destination.stat().st_size)}")
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

        def writer(group: list[int]):
            def write(staged: Path) -> None:
                out = pymupdf.open()
                try:
                    out.insert_pdf(doc, from_page=group[0] - 1, to_page=group[-1] - 1)
                    if len(group) != group[-1] - group[0] + 1:
                        out.select([page - group[0] for page in group])
                    out.save(staged)
                finally:
                    out.close()

            return write

        for group, destination in zip(groups, destinations, strict=True):
            stage_and_move(destination, writer(group))
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
        stage_and_move(destination, doc.save)
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
    expected_pages = _page_count(source)
    reporter.start(("compressing", "compressed"), f"{source.name}  {quality}", None)
    sizes: dict[str, int] = {}

    def write(staged: Path) -> None:
        result = subprocess.run(
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
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            message = detail[-1] if detail else f"ghostscript exited {result.returncode}"
            raise BadInput(f"ghostscript failed compressing {source.name}: {message}")
        _validate_gs_output(staged, expected_pages)
        sizes["after"] = staged.stat().st_size
        if sizes["after"] >= before:
            # Compression made it bigger; stage the original instead, so the
            # destination is still written exactly once.
            shutil.copyfile(source, staged)

    stage_and_move(destination, write)
    after = sizes["after"]
    if after >= before:
        reporter.finish(
            f"{destination}  {human_size(before)} → {human_size(after)}; kept original (compression made it larger)"
        )
    else:
        reporter.finish(f"{destination}  {human_size(before)} → {human_size(after)}")
    return [destination]
