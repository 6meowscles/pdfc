import pymupdf
import pytest
from click.testing import CliRunner

from pdfc import deps
from pdfc.cli import main
from pdfc.converters import pdfops
from pdfc.errors import BadInput
from pdfc.progress import NullReporter


def pdf_with(path, page_count):
    doc = pymupdf.open()
    for number in range(1, page_count + 1):
        doc.new_page().insert_text((72, 72), f"Page {number}", fontsize=12)
    doc.save(path)
    doc.close()
    return path


def page_count(path):
    with pymupdf.open(path) as doc:
        return doc.page_count


def test_merge_concatenates_in_argument_order(tmp_path):
    first = pdf_with(tmp_path / "a.pdf", 2)
    second = pdf_with(tmp_path / "b.pdf", 3)
    out = tmp_path / "all.pdf"
    pdfops.merge([first, second], out, NullReporter(), force=False)
    assert page_count(out) == 5


def test_merge_rejects_a_non_pdf_input(tmp_path, sample_png):
    with pytest.raises(BadInput, match="not a PDF"):
        pdfops.merge([sample_png], tmp_path / "out.pdf", NullReporter(), force=False)


def test_split_by_page_selection(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 10)
    out = tmp_path / "sel.pdf"
    pdfops.split(source, out, pages="1-3,9", every=None, each=False, reporter=NullReporter(), force=False)
    assert page_count(out) == 4


def test_split_every_n_writes_chunks(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 5)
    outputs = pdfops.split(
        source, tmp_path / "out", pages=None, every=2, each=False, reporter=NullReporter(), force=False
    )
    assert len(outputs) == 3
    assert [page_count(p) for p in outputs] == [2, 2, 1]


def test_split_each_writes_one_file_per_page(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 4)
    outputs = pdfops.split(
        source, tmp_path / "out", pages=None, every=None, each=True, reporter=NullReporter(), force=False
    )
    assert len(outputs) == 4
    assert all(page_count(p) == 1 for p in outputs)


def test_split_requires_exactly_one_mode(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 4)
    with pytest.raises(BadInput, match="exactly one of"):
        pdfops.split(source, tmp_path / "o.pdf", pages="1", every=2, each=False, reporter=NullReporter(), force=False)
    with pytest.raises(BadInput, match="exactly one of"):
        pdfops.split(source, tmp_path / "o.pdf", pages=None, every=None, each=False, reporter=NullReporter(), force=False)


def test_rotate_changes_page_rotation(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 2)
    out = tmp_path / "rot.pdf"
    pdfops.rotate(source, out, angle=90, pages=None, reporter=NullReporter(), force=False)
    with pymupdf.open(out) as doc:
        assert doc[0].rotation == 90 and doc[1].rotation == 90


def test_rotate_can_target_specific_pages(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 3)
    out = tmp_path / "rot.pdf"
    pdfops.rotate(source, out, angle=180, pages="2", reporter=NullReporter(), force=False)
    with pymupdf.open(out) as doc:
        assert doc[0].rotation == 0 and doc[1].rotation == 180


def test_rotate_rejects_an_unsupported_angle(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 1)
    with pytest.raises(BadInput, match="angle"):
        pdfops.rotate(source, tmp_path / "o.pdf", angle=45, pages=None, reporter=NullReporter(), force=False)


def test_extract_pages_writes_one_file(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 10)
    outputs = pdfops.extract_pages(source, tmp_path / "out.pdf", "2-4", NullReporter(), force=False)
    assert len(outputs) == 1 and page_count(outputs[0]) == 3


def test_refusing_to_overwrite_without_force(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"
    out.write_text("existing")
    with pytest.raises(BadInput, match="already exists"):
        pdfops.extract_pages(source, out, "1", NullReporter(), force=False)
    pdfops.extract_pages(source, out, "1", NullReporter(), force=True)


@pytest.mark.needs_gs
@pytest.mark.skipif(not deps.have("gs"), reason="ghostscript not installed")
def test_compress_produces_a_valid_pdf(tmp_path):
    source = pdf_with(tmp_path / "in.pdf", 3)
    out = tmp_path / "small.pdf"
    pdfops.compress(source, out, quality="ebook", reporter=NullReporter(), force=False)
    assert out.read_bytes().startswith(b"%PDF")
    assert page_count(out) == 3


def test_merge_command_is_reachable_from_the_cli(tmp_path):
    first = pdf_with(tmp_path / "a.pdf", 1)
    second = pdf_with(tmp_path / "b.pdf", 1)
    out = tmp_path / "all.pdf"
    try:
        runner = CliRunner(mix_stderr=False)
    except TypeError:
        runner = CliRunner()
    result = runner.invoke(main, ["merge", str(first), str(second), "-o", str(out)])
    assert result.exit_code == 0
    assert page_count(out) == 2
