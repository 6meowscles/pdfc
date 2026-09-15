import shutil
import subprocess
import tempfile
from pathlib import Path

from pdfc import deps
from pdfc.errors import BadInput
from pdfc.formats import OFFICE, Format
from pdfc.planning import Step, output_paths
from pdfc.progress import human_size
from pdfc.registry import converter


# LibreOffice chooses its import filter from the file extension, and for .html
# it picks Writer/Web -- a module with no Word or ODF Text export filter, so the
# conversion fails with "no export filter" or, worse, silently writes nothing.
# Naming the Writer importer is what makes html -> docx work at all.
HTML_IN_WRITER = "HTML (StarWriter)"

# Export filters are named explicitly for the same reason: a bare "docx"
# resolves against whichever module loaded the document.
WRITER_EXPORT = {"docx": "MS Word 2007 XML", "odt": "writer8"}


def _libreoffice_convert(
    step: Step, extension: str, infilter: str | None = None
) -> None:
    binary = deps.require("libreoffice", step.edge.label)
    destination = output_paths(step.target, step.origin.stem, 1, extension)[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    step.reporter.start(step.edge.verbs, step.edge.label, None)
    export = WRITER_EXPORT.get(extension) if infilter else None
    target_spec = f"{extension}:{export}" if export else extension
    with tempfile.TemporaryDirectory(prefix="pdfc-lo-") as scratch:
        profile = Path(scratch) / "profile"
        outdir = Path(scratch) / "out"
        outdir.mkdir()
        command = [
            binary,
            "--headless",
            f"-env:UserInstallation=file://{profile}",
        ]
        if infilter:
            command.append(f"--infilter={infilter}")
        command += ["--convert-to", target_spec, "--outdir", str(outdir), str(step.source)]
        result = subprocess.run(command, capture_output=True, text=True)
        produced = list(outdir.glob(f"*.{extension}"))
        if result.returncode != 0 or not produced:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            message = detail[-1] if detail else "libreoffice produced no output"
            raise BadInput(f"libreoffice failed converting {step.source.name}: {message}")
        shutil.move(str(produced[0]), destination)
    step.outputs.append(destination)
    step.reporter.finish(step.summary(human_size(destination.stat().st_size)))


def _register() -> None:
    for fmt in sorted(OFFICE, key=lambda f: f.value):
        converter(fmt, Format.PDF, requires=("libreoffice",), cost=2)(
            lambda step: _libreoffice_convert(step, "pdf")
        )
    # There is deliberately no pdf -> docx edge. LibreOffice loads a PDF into
    # Draw, which has no Writer export filter, so that conversion can never
    # succeed -- it was previously advertised as available and failed every
    # time it was attempted. Writer formats are reachable from html instead,
    # which puts md -> html -> docx within the two-hop routing limit.
    for extension, target in (("docx", Format.DOCX), ("odt", Format.ODT)):
        converter(Format.HTML, target, requires=("libreoffice",), cost=2)(
            lambda step, extension=extension: _libreoffice_convert(
                step, extension, infilter=HTML_IN_WRITER
            )
        )


_register()
