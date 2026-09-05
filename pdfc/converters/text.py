import html as html_module
import statistics

import markdown
import pymupdf

from pdfc import deps
from pdfc.errors import MissingDependency
from pdfc.formats import Format
from pdfc.planning import Step, output_paths
from pdfc.progress import human_size
from pdfc.registry import converter

MIN_CHARS_PER_PAGE = 50

PAGE_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; }
pre { white-space: pre-wrap; font-family: monospace; font-size: 10pt; }
table { border-collapse: collapse; }
td, th { border: 1px solid #999; padding: 4px 8px; }
"""


def _single_target(step: Step, extension: str):
    path = output_paths(step.target, step.origin.stem, 1, extension)[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _warn_if_scanned(step: Step, text: str, page_count: int) -> None:
    if page_count and len(text.strip()) / page_count < MIN_CHARS_PER_PAGE:
        step.reporter.warn(
            f"{step.source.name} has almost no extractable text; it looks scanned — try `pdfc ocr`"
        )


@converter(Format.PDF, Format.TXT, verbs=("extracting", "extracted"))
def pdf_to_txt(step: Step) -> None:
    destination = _single_target(step, "txt")
    with pymupdf.open(step.source) as doc:
        step.reporter.start(step.edge.verbs, step.edge.label, doc.page_count)
        chunks = []
        for page in doc:
            chunks.append(page.get_text("text"))
            step.reporter.advance()
        page_count = doc.page_count
    text = "\n\n".join(chunks)
    destination.write_text(text, encoding="utf-8")
    step.outputs.append(destination)
    _warn_if_scanned(step, text, page_count)
    step.reporter.finish(step.summary(f"{len(text)} chars"))


@converter(Format.PDF, Format.MD, verbs=("extracting", "extracted"))
def pdf_to_md(step: Step) -> None:
    destination = _single_target(step, "md")
    lines: list[str] = []
    with pymupdf.open(step.source) as doc:
        step.reporter.start(step.edge.verbs, step.edge.label, doc.page_count)
        for page in doc:
            lines.extend(_page_to_markdown(page))
            lines.append("")
            step.reporter.advance()
        page_count = doc.page_count
    text = "\n".join(lines).strip() + "\n"
    destination.write_text(text, encoding="utf-8")
    step.outputs.append(destination)
    _warn_if_scanned(step, text, page_count)
    step.reporter.finish(step.summary(f"{len(text)} chars"))


def _page_to_markdown(page) -> list[str]:
    """Map font sizes above the page median onto heading levels."""
    data = page.get_text("dict")
    spans = [
        span
        for block in data["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span["text"].strip()
    ]
    if not spans:
        return []
    median = statistics.median(span["size"] for span in spans)
    lines: list[str] = []
    for block in data["blocks"]:
        text_lines = [
            "".join(span["text"] for span in line.get("spans", [])).strip()
            for line in block.get("lines", [])
        ]
        text = " ".join(part for part in text_lines if part)
        if not text:
            continue
        sizes = [
            span["size"]
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        ]
        largest = max(sizes) if sizes else median
        if largest >= median * 1.5:
            lines.append(f"# {text}")
        elif largest >= median * 1.2:
            lines.append(f"## {text}")
        else:
            lines.append(text)
        lines.append("")
    return lines


@converter(Format.MD, Format.HTML)
def md_to_html(step: Step) -> None:
    destination = _single_target(step, "html")
    step.reporter.start(step.edge.verbs, step.edge.label, 1)
    body = markdown.markdown(
        step.source.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    destination.write_text(_document(step.origin.stem, body), encoding="utf-8")
    step.outputs.append(destination)
    step.reporter.advance()
    step.reporter.finish(step.summary(human_size(destination.stat().st_size)))


@converter(Format.TXT, Format.HTML)
def txt_to_html(step: Step) -> None:
    destination = _single_target(step, "html")
    step.reporter.start(step.edge.verbs, step.edge.label, 1)
    escaped = html_module.escape(step.source.read_text(encoding="utf-8"))
    destination.write_text(
        _document(step.origin.stem, f"<pre>{escaped}</pre>"), encoding="utf-8"
    )
    step.outputs.append(destination)
    step.reporter.advance()
    step.reporter.finish(step.summary(human_size(destination.stat().st_size)))


def _document(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html_module.escape(title)}</title>"
        f"<style>{PAGE_CSS}</style></head><body>{body}</body></html>"
    )


@converter(Format.HTML, Format.PDF)
def html_to_pdf(step: Step) -> None:
    # weasyprint needs pango and cairo at import time; report that like any
    # other missing dependency instead of letting the ImportError escape.
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise MissingDependency(
            "weasyprint (needs pango and cairo)",
            deps.install_hint("pango"),
            step.edge.label,
        ) from error

    destination = _single_target(step, "pdf")
    step.reporter.start(step.edge.verbs, step.edge.label, None)
    HTML(filename=str(step.source), base_url=str(step.source.parent)).write_pdf(str(destination))
    step.outputs.append(destination)
    step.reporter.finish(step.summary(human_size(destination.stat().st_size)))
