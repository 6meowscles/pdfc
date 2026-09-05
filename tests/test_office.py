import pytest

from pdfc import deps
from pdfc.errors import MissingDependency
from pdfc.formats import Format
from pdfc.planning import build_plan, execute
from pdfc.progress import NullReporter
from pdfc.registry import REGISTRY, load_converters

has_libreoffice = deps.have("libreoffice")


@pytest.fixture(autouse=True)
def loaded():
    load_converters()


def test_office_edges_are_registered():
    sources = {(e.source, e.target) for e in REGISTRY.edges()}
    for fmt in (Format.DOCX, Format.ODT, Format.PPTX, Format.XLSX):
        assert (fmt, Format.PDF) in sources
    assert (Format.PDF, Format.DOCX) in sources


def test_office_edges_declare_libreoffice():
    for edge in REGISTRY.edges():
        if edge.source is Format.DOCX and edge.target is Format.PDF:
            assert edge.requires == ("libreoffice",)


@pytest.mark.skipif(has_libreoffice, reason="libreoffice is installed here")
def test_missing_libreoffice_is_reported_as_a_dependency_error():
    with pytest.raises(MissingDependency) as caught:
        REGISTRY.route(Format.DOCX, Format.PDF, deps.have)
    assert "libreoffice" in str(caught.value)


def test_docx_to_png_routes_through_pdf():
    route = REGISTRY.route(Format.DOCX, Format.PNG, lambda _b: True)
    assert [e.target for e in route] == [Format.PDF, Format.PNG]


@pytest.mark.needs_libreoffice
@pytest.mark.skipif(not has_libreoffice, reason="libreoffice not installed")
def test_docx_to_pdf_produces_a_pdf(tmp_path):
    import zipfile

    source = tmp_path / "doc.docx"
    # Minimal valid docx written by libreoffice itself would be ideal; build one here.
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Hello from docx</w:t></w:r></w:p></w:body></w:document>",
        )
    route = REGISTRY.route(Format.DOCX, Format.PDF, deps.have)
    plan = build_plan(route, source, tmp_path / "out.pdf", {}, NullReporter(), tmp_path)
    outputs = execute(plan)
    assert outputs[0].read_bytes().startswith(b"%PDF")
