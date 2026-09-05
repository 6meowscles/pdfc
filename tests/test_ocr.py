import pymupdf
import pytest

from pdfc import deps
from pdfc.converters import ocr
from pdfc.errors import MissingDependency
from pdfc.progress import NullReporter

pytestmark = pytest.mark.needs_tesseract

skip_without_tesseract = pytest.mark.skipif(
    not deps.have("tesseract"), reason="tesseract not installed"
)


class Recording(NullReporter):
    def __init__(self):
        super().__init__()
        self.events = []

    def start(self, verbs, label, total):
        self.events.append(("start", verbs))

    def finish(self, summary):
        self.events.append(("finish", summary))


def scanned_pdf(path):
    """A PDF whose text is drawn as an image, so it has no extractable text layer."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 400), "white")
    ImageDraw.Draw(image).text((40, 160), "HELLO OCR WORLD", fill="black")
    image = image.resize((2400, 800))
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    png = path.parent / "scan.png"
    image.save(png)
    page.insert_image(page.rect, filename=str(png))
    doc.save(path)
    doc.close()
    return path


@skip_without_tesseract
def test_available_languages_includes_eng():
    assert "eng" in ocr.available_languages()


@skip_without_tesseract
def test_validate_language_accepts_eng():
    ocr.validate_language("eng")


@skip_without_tesseract
def test_validate_language_rejects_a_missing_pack():
    with pytest.raises(MissingDependency) as caught:
        ocr.validate_language("zzz")
    assert "zzz" in str(caught.value)


@skip_without_tesseract
def test_ocr_adds_a_text_layer(tmp_path):
    source = scanned_pdf(tmp_path / "scan.pdf")
    with pymupdf.open(source) as doc:
        assert doc[0].get_text().strip() == ""
    out = tmp_path / "searchable.pdf"
    ocr.run_ocr(source, out, "eng", force_ocr=False, reporter=NullReporter(), force=False)
    with pymupdf.open(out) as doc:
        assert "OCR" in doc[0].get_text().upper()


@skip_without_tesseract
def test_ocr_uses_the_i_see_you_verbs(tmp_path):
    source = scanned_pdf(tmp_path / "scan.pdf")
    reporter = Recording()
    ocr.run_ocr(source, tmp_path / "out.pdf", "eng", False, reporter, force=False)
    assert reporter.events[0] == ("start", ("I SEE YOU", "I SAW YOU"))
    assert reporter.events[-1][0] == "finish"


@skip_without_tesseract
def test_ocr_to_text_target_writes_text(tmp_path):
    source = scanned_pdf(tmp_path / "scan.pdf")
    out = tmp_path / "out.txt"
    outputs = ocr.run_ocr(source, out, "eng", False, NullReporter(), force=False)
    assert outputs[0].suffix == ".txt"
    assert "OCR" in outputs[0].read_text().upper()
