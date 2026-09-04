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


def test_text_rich_pdf_does_not_warn(sample_pdf, tmp_path):
    reporter = Recording()
    convert(Format.PDF, Format.TXT, sample_pdf, tmp_path / "out.txt", tmp_path, reporter)
    assert reporter.warnings == []
