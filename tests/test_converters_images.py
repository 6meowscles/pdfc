import pymupdf
import pytest
from PIL import Image

from pdfc import deps
from pdfc.formats import Format
from pdfc.planning import build_plan, execute
from pdfc.progress import NullReporter
from pdfc.registry import REGISTRY, load_converters


@pytest.fixture(autouse=True)
def loaded():
    load_converters()


def convert(source, target, tmp_path, **options):
    route = REGISTRY.route(
        Format(source.suffix.lstrip(".").replace("jpg", "jpeg")),
        Format(target.suffix.lstrip(".").replace("jpg", "jpeg")),
        deps.have,
    )
    options.setdefault("dpi", 150)
    plan = build_plan(route, source, target, options, NullReporter(), tmp_path)
    return execute(plan)


def test_pdf_to_png_writes_one_file_per_page(sample_pdf, tmp_path):
    outputs = convert(sample_pdf, tmp_path / "page.png", tmp_path)
    assert len(outputs) == 3
    assert [p.name for p in outputs] == ["page-001.png", "page-002.png", "page-003.png"]
    assert all(p.exists() for p in outputs)


def test_pdf_to_png_honours_dpi(sample_pdf, tmp_path):
    low = convert(sample_pdf, tmp_path / "low.png", tmp_path, dpi=72)
    high = convert(sample_pdf, tmp_path / "high.png", tmp_path, dpi=200)
    assert Image.open(high[0]).width > Image.open(low[0]).width


def test_pdf_to_jpeg_and_webp_produce_readable_images(sample_pdf, tmp_path):
    for name, expected in (("out.jpg", "JPEG"), ("out.webp", "WEBP")):
        outputs = convert(sample_pdf, tmp_path / name, tmp_path)
        assert Image.open(outputs[0]).format == expected


def test_png_to_pdf_produces_a_one_page_pdf(sample_png, tmp_path):
    outputs = convert(sample_png, tmp_path / "out.pdf", tmp_path)
    assert len(outputs) == 1
    with pymupdf.open(outputs[0]) as doc:
        assert doc.page_count == 1


def test_png_to_pdf_output_starts_with_the_pdf_header(sample_png, tmp_path):
    outputs = convert(sample_png, tmp_path / "out.pdf", tmp_path)
    assert outputs[0].read_bytes().startswith(b"%PDF")


def test_pdf_to_png_reports_progress_through_the_reporter(sample_pdf, tmp_path):
    class Recording(NullReporter):
        def __init__(self):
            super().__init__()
            self.events = []

        def start(self, verbs, label, total):
            self.events.append(("start", verbs, total))

        def advance(self, n=1):
            self.events.append(("advance", n))

        def finish(self, summary):
            self.events.append(("finish", summary))

    reporter = Recording()
    route = REGISTRY.route(Format.PDF, Format.PNG, deps.have)
    plan = build_plan(route, sample_pdf, tmp_path / "p.png", {"dpi": 100}, reporter, tmp_path)
    execute(plan)
    kinds = [event[0] for event in reporter.events]
    assert kinds[0] == "start" and kinds[-1] == "finish"
    assert reporter.events[0][1] == ("rendering", "rendered")
    assert reporter.events[0][2] == 3
    assert kinds.count("advance") == 3
