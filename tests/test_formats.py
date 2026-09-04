from pathlib import Path

import pytest

from pdfc import formats
from pdfc.errors import BadInput
from pdfc.formats import Format


def test_format_values_are_lowercase_names():
    assert Format.MD.value == "md"
    assert Format.PDF.value == "pdf"


def test_from_name_accepts_aliases_and_rejects_junk():
    assert formats.from_name("pdf") is Format.PDF
    assert formats.from_name("JPG") is Format.JPEG
    with pytest.raises(BadInput, match="unknown format"):
        formats.from_name("docx2")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("a.pdf", Format.PDF),
        ("a.PDF", Format.PDF),
        ("a.jpg", Format.JPEG),
        ("a.jpeg", Format.JPEG),
        ("a.tif", Format.TIFF),
        ("a.markdown", Format.MD),
        ("a.htm", Format.HTML),
        ("a.xlsx", Format.XLSX),
        ("a.bogus", None),
        ("noextension", None),
    ],
)
def test_from_extension(name, expected):
    assert formats.from_extension(Path(name)) is expected


def test_sniff_reads_magic_bytes_not_the_extension(sample_pdf, tmp_path):
    disguised = tmp_path / "actually.txt"
    disguised.write_bytes(sample_pdf.read_bytes())
    assert formats.sniff(disguised) is Format.PDF


def test_sniff_detects_png(sample_png):
    assert formats.sniff(sample_png) is Format.PNG


def test_sniff_detects_docx_by_zip_contents(tmp_path):
    import zipfile

    path = tmp_path / "doc.bin"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "wordprocessingml.document")
        archive.writestr("word/document.xml", "<w:document/>")
    assert formats.sniff(path) is Format.DOCX


def test_sniff_returns_none_for_missing_or_unknown(tmp_path):
    assert formats.sniff(tmp_path / "nope") is None
    unknown = tmp_path / "unknown.bin"
    unknown.write_bytes(b"\x00\x01\x02\x03")
    assert formats.sniff(unknown) is None


def test_detect_input_prefers_override_then_magic_then_extension(sample_pdf, tmp_path):
    assert formats.detect_input(sample_pdf, Format.TXT) is Format.TXT
    disguised = tmp_path / "actually.txt"
    disguised.write_bytes(sample_pdf.read_bytes())
    assert formats.detect_input(disguised, None) is Format.PDF
    plain = tmp_path / "notes.md"
    plain.write_text("# hi")
    assert formats.detect_input(plain, None) is Format.MD


def test_detect_input_rejects_the_undetectable(tmp_path):
    path = tmp_path / "mystery"
    path.write_bytes(b"\x00\x01")
    with pytest.raises(BadInput, match="cannot tell what format"):
        formats.detect_input(path, None)


def test_detect_output_uses_extension_and_ignores_magic(tmp_path):
    assert formats.detect_output(tmp_path / "out.png", None) is Format.PNG
    assert formats.detect_output(tmp_path / "out.png", Format.JPEG) is Format.JPEG
    with pytest.raises(BadInput, match="cannot tell what format"):
        formats.detect_output(tmp_path / "out", None)
