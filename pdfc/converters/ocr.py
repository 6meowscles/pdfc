import subprocess
import tempfile
from pathlib import Path

from pdfc import deps, formats
from pdfc.errors import BadInput, MissingDependency
from pdfc.formats import Format
from pdfc.planning import check_writable, output_paths, stage_and_move
from pdfc.progress import Reporter, human_size

VERBS = ("I SEE YOU", "I SAW YOU")


def available_languages() -> set[str]:
    binary = deps.require("tesseract", "ocr")
    result = subprocess.run([binary, "--list-langs"], capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        message = detail[-1] if detail else f"tesseract exited {result.returncode}"
        raise BadInput(f"tesseract could not list its languages: {message}")
    lines = result.stdout.splitlines()
    return {line.strip() for line in lines[1:] if line.strip()}


def validate_language(language: str) -> None:
    if language not in available_languages():
        raise MissingDependency(
            f"tesseract language pack {language!r}",
            f"sudo pacman -S tesseract-data-{language}",
            "ocr",
        )


def ocr_to_pdf(
    source: Path, target: Path, language: str, force_ocr: bool, reporter: Reporter, force: bool
) -> Path:
    # ocrmypdf is optional in some installs (it is an AUR package on Arch, and a
    # separate pip install elsewhere), so report its absence the way every other
    # missing dependency is reported rather than letting the ImportError escape.
    try:
        import ocrmypdf
    except ImportError as error:
        raise MissingDependency(
            "ocrmypdf",
            "paru -S ocrmypdf   (or: pip install ocrmypdf)",
            "ocr",
        ) from error

    deps.require("tesseract", "ocr")
    deps.require("gs", "ocr")
    validate_language(language)
    check_writable([target], force)
    reporter.start(VERBS, f"{source.name}  {language}", None)

    def write(staged: Path) -> None:
        ocrmypdf.ocr(
            source,
            staged,
            language=language,
            force_ocr=force_ocr,
            skip_text=not force_ocr,
            progress_bar=False,
        )

    return stage_and_move(target, write)


def run_ocr(
    source: Path, target: Path, language: str, force_ocr: bool, reporter: Reporter, force: bool
) -> list[Path]:
    if not source.exists():
        raise BadInput(f"cannot read {source}")
    target_format = formats.detect_output(target, None)

    if target_format is Format.PDF:
        destination = output_paths(target, source.stem, 1, "pdf")[0]
        ocr_to_pdf(source, destination, language, force_ocr, reporter, force)
        reporter.finish(f"{destination}  {human_size(destination.stat().st_size)}")
        return [destination]

    if target_format not in (Format.TXT, Format.MD):
        raise BadInput(
            f"ocr can write pdf, txt, or md; {target_format.value} is not one of them"
        )

    # The route through a temp PDF cannot reject an existing output until the
    # OCR has already run, so check it up front.
    check_writable([target], force)

    from pdfc.cli import run_conversion

    with tempfile.TemporaryDirectory(prefix="pdfc-ocr-") as scratch:
        staged = Path(scratch) / "searchable.pdf"
        ocr_to_pdf(source, staged, language, force_ocr, reporter, force=True)
        reporter.finish(f"recognised {source.name}")
        return run_conversion(
            source=staged,
            target=target,
            from_fmt="pdf",
            to_fmt=target_format.value,
            options={"force": force},
            force=force,
            progress_mode="none",
        )
