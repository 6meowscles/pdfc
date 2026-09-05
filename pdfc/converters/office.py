import shutil
import subprocess
import tempfile
from pathlib import Path

from pdfc import deps
from pdfc.errors import BadInput
from pdfc.formats import OFFICE, Format
from pdfc.planning import Step, output_paths
from pdfc.registry import converter


def _libreoffice_convert(step: Step, extension: str) -> None:
    binary = deps.require("libreoffice", step.edge.label)
    destination = output_paths(step.target, step.source.stem, 1, extension)[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    step.reporter.start(step.edge.verbs, step.edge.label, None)
    with tempfile.TemporaryDirectory(prefix="pdfc-lo-") as scratch:
        profile = Path(scratch) / "profile"
        outdir = Path(scratch) / "out"
        outdir.mkdir()
        result = subprocess.run(
            [
                binary,
                "--headless",
                f"-env:UserInstallation=file://{profile}",
                "--convert-to",
                extension,
                "--outdir",
                str(outdir),
                str(step.source),
            ],
            capture_output=True,
            text=True,
        )
        produced = list(outdir.glob(f"*.{extension}"))
        if result.returncode != 0 or not produced:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            message = detail[-1] if detail else "libreoffice produced no output"
            raise BadInput(f"libreoffice failed converting {step.source.name}: {message}")
        shutil.move(str(produced[0]), destination)
    step.outputs.append(destination)
    step.reporter.finish(f"{step.destination_hint}  {destination.stat().st_size} B")


def _register() -> None:
    for fmt in sorted(OFFICE, key=lambda f: f.value):
        converter(fmt, Format.PDF, requires=("libreoffice",), cost=2)(
            lambda step: _libreoffice_convert(step, "pdf")
        )
    converter(Format.PDF, Format.DOCX, requires=("libreoffice",), cost=2)(
        lambda step: _libreoffice_convert(step, "docx")
    )


_register()
