import pymupdf
import pytest

from pdfc import deps
from pdfc.formats import Format
from pdfc.planning import build_plan, execute
from pdfc.progress import NullReporter
from pdfc.registry import REGISTRY, load_converters


@pytest.fixture(autouse=True)
def loaded():
    load_converters()


class Recording(NullReporter):
    def __init__(self):
        super().__init__()
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)


def convert(source_fmt, target_fmt, source, target, tmp_path, reporter=None):
    route = REGISTRY.route(source_fmt, target_fmt, deps.have)
    plan = build_plan(route, source, target, {}, reporter or NullReporter(), tmp_path)
    return execute(plan)


def _pdf_with_page_text(tmp_path, texts, name="generated.pdf"):
    """Build a PDF with one page per string in `texts`, each page holding that text.

    Kept local to this file (rather than added to tests/conftest.py) so it doesn't
    disturb other tests that assert on sample_pdf's exact content and page count.
    """
    path = tmp_path / name
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()
    return path


def test_pdf_to_txt_extracts_the_page_text(sample_pdf, tmp_path):
    outputs = convert(Format.PDF, Format.TXT, sample_pdf, tmp_path / "out.txt", tmp_path)
    text = outputs[0].read_text()
    assert "Page 1 of the sample document." in text
    assert "Page 3 of the sample document." in text


def test_pdf_to_md_produces_markdown(sample_pdf, tmp_path):
    outputs = convert(Format.PDF, Format.MD, sample_pdf, tmp_path / "out.md", tmp_path)
    assert "Page 1 of the sample document." in outputs[0].read_text()


def test_md_to_html_renders_headings(sample_md, tmp_path):
    outputs = convert(Format.MD, Format.HTML, sample_md, tmp_path / "out.html", tmp_path)
    html = outputs[0].read_text()
    assert "<h1>" in html and "Heading" in html


def test_txt_to_html_preserves_text_in_a_pre_block(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("line one\nline two\n")
    outputs = convert(Format.TXT, Format.HTML, source, tmp_path / "out.html", tmp_path)
    html = outputs[0].read_text()
    assert "<pre" in html and "line two" in html


def test_html_to_pdf_produces_a_valid_pdf(tmp_path):
    source = tmp_path / "in.html"
    source.write_text("<h1>Title</h1><p>Body text.</p>")
    outputs = convert(Format.HTML, Format.PDF, source, tmp_path / "out.pdf", tmp_path)
    assert outputs[0].read_bytes().startswith(b"%PDF")
    with pymupdf.open(outputs[0]) as doc:
        assert doc.page_count >= 1


def test_md_to_pdf_routes_through_html_in_two_hops(sample_md, tmp_path):
    route = REGISTRY.route(Format.MD, Format.PDF, deps.have)
    assert [e.target for e in route] == [Format.HTML, Format.PDF]
    outputs = convert(Format.MD, Format.PDF, sample_md, tmp_path / "out.pdf", tmp_path)
    with pymupdf.open(outputs[0]) as doc:
        assert "Heading" in doc[0].get_text()


def test_scanned_pdf_warns_about_ocr(tmp_path):
    blank = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    doc.save(blank)
    doc.close()
    reporter = Recording()
    convert(Format.PDF, Format.TXT, blank, tmp_path / "out.txt", tmp_path, reporter)
    assert any("pdfc ocr" in w for w in reporter.warnings)


def test_text_rich_pdf_does_not_warn(tmp_path):
    pages = [
        "This page holds a full paragraph of real body text, well over fifty characters long.",
        "Another page with plenty of readable prose to keep the average comfortably high.",
        "A third page carries just as much text as the first two, so no page looks thin.",
    ]
    pdf = _pdf_with_page_text(tmp_path, pages)
    reporter = Recording()
    convert(Format.PDF, Format.TXT, pdf, tmp_path / "out.txt", tmp_path, reporter)
    assert reporter.warnings == []


def test_scanned_guard_pins_the_boundary(tmp_path):
    # Single-page PDFs where the extracted text is exactly 49 vs. 51 characters,
    # straddling the MIN_CHARS_PER_PAGE = 50 threshold on either side.
    just_under = _pdf_with_page_text(tmp_path, ["x" * 49], name="just_under.pdf")
    just_over = _pdf_with_page_text(tmp_path, ["x" * 51], name="just_over.pdf")

    under_reporter = Recording()
    convert(Format.PDF, Format.TXT, just_under, tmp_path / "under.txt", tmp_path, under_reporter)
    assert any("pdfc ocr" in w for w in under_reporter.warnings)

    over_reporter = Recording()
    convert(Format.PDF, Format.TXT, just_over, tmp_path / "over.txt", tmp_path, over_reporter)
    assert over_reporter.warnings == []


def test_directory_target_names_the_output_after_the_original_input(sample_md, tmp_path):
    """A two-hop md -> html -> pdf run into a directory must be named for the
    user's input, not for the scratch file the last hop happens to read."""
    outdir = tmp_path / "outdir"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outputs = convert(Format.MD, Format.PDF, sample_md, outdir, scratch)
    assert outputs == [outdir / "sample.pdf"]
    assert outputs[0].read_bytes().startswith(b"%PDF")


def test_single_hop_into_a_directory_also_uses_the_input_stem(sample_md, tmp_path):
    outdir = tmp_path / "html"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outputs = convert(Format.MD, Format.HTML, sample_md, outdir, scratch)
    assert outputs == [outdir / "sample.html"]


def test_intermediate_scratch_paths_never_reach_the_terminal(sample_md, tmp_path):
    import io

    from pdfc.progress import PlainReporter

    stream = io.StringIO()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    target = tmp_path / "out.pdf"
    convert(Format.MD, Format.PDF, sample_md, target, scratch, PlainReporter(stream, 9))
    printed = stream.getvalue()
    assert "step0" not in printed
    assert str(scratch) not in printed
    assert str(target) in printed


def test_non_ascii_content_round_trips_through_md_to_html(tmp_path):
    source = tmp_path / "resume.md"
    source.write_text("# Résumé\n\nCafé — naïve façade, 日本語.\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outputs = convert(Format.MD, Format.HTML, source, tmp_path / "out.html", scratch)
    raw = outputs[0].read_bytes()
    # The document declares utf-8, so the bytes on disk must actually be utf-8.
    assert b"charset='utf-8'" in raw
    assert "Café — naïve façade, 日本語.".encode() in raw
    assert "Résumé" in outputs[0].read_text(encoding="utf-8")


def test_non_ascii_content_round_trips_through_pdf_to_txt(tmp_path):
    pdf = _pdf_with_page_text(tmp_path, ["Café naïve — Résumé"], name="accents.pdf")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    outputs = convert(Format.PDF, Format.TXT, pdf, tmp_path / "out.txt", scratch)
    assert "Café" in outputs[0].read_text(encoding="utf-8")
