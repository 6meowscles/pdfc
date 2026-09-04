import pymupdf
from PIL import Image

from pdfc.formats import RASTER, Format
from pdfc.planning import Step, output_paths
from pdfc.registry import converter

# Pillow's format name for each raster Format.
PIL_FORMATS = {
    Format.PNG: "PNG",
    Format.JPEG: "JPEG",
    Format.WEBP: "WEBP",
    Format.TIFF: "TIFF",
}


def _render(step: Step, target_format: Format) -> None:
    dpi = int(step.options.get("dpi", 150))
    with pymupdf.open(step.source) as doc:
        count = doc.page_count
        paths = output_paths(step.target, step.source.stem, count, target_format.value)
        step.reporter.start(step.edge.verbs, step.edge.label, count)
        for page, path in zip(doc, paths, strict=True):
            pixmap = page.get_pixmap(dpi=dpi)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path, PIL_FORMATS[target_format])
            step.outputs.append(path)
            step.reporter.advance()
    total = sum(p.stat().st_size for p in step.outputs)
    step.reporter.finish(f"{len(step.outputs)} files → {step.destination_hint}  {_size(total)}")


def _to_pdf(step: Step) -> None:
    step.reporter.start(step.edge.verbs, step.edge.label, 1)
    paths = output_paths(step.target, step.source.stem, 1, "pdf")
    destination = paths[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(step.source) as image:
        frames = [frame.convert("RGB") for frame in _frames(image)]
    frames[0].save(destination, "PDF", save_all=True, append_images=frames[1:])
    step.outputs.append(destination)
    step.reporter.advance()
    step.reporter.finish(f"{step.destination_hint}  {_size(destination.stat().st_size)}")


def _frames(image: Image.Image) -> list[Image.Image]:
    """Every frame of a multi-page TIFF, or the single frame of anything else."""
    frames = []
    index = 0
    while True:
        try:
            image.seek(index)
        except EOFError:
            break
        frames.append(image.copy())
        index += 1
    return frames or [image.copy()]


def _size(byte_count: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if byte_count < 1024 or unit == "GB":
            return f"{byte_count:.1f} {unit}" if unit != "B" else f"{byte_count} B"
        byte_count /= 1024
    return f"{byte_count:.1f} GB"


def _register() -> None:
    for raster in sorted(RASTER, key=lambda f: f.value):
        converter(
            Format.PDF, raster, cost=1, verbs=("rendering", "rendered")
        )(lambda step, fmt=raster: _render(step, fmt))
        converter(raster, Format.PDF, cost=1, verbs=("converting", "converted"))(_to_pdf)


_register()
