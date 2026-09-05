import subprocess
from pathlib import Path

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


def page_texts(path):
    with pymupdf.open(path) as doc:
        return [page.get_text().strip() for page in doc]


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
    assert page_texts(out) == ["Page 1", "Page 2", "Page 3", "Page 9"]


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


def test_compress_rejects_a_corrupt_ghostscript_output(tmp_path, monkeypatch):
    """Ghostscript can exit 0 while writing an empty or truncated file. Stub it
    doing exactly that and confirm compress() refuses to treat it as a result."""
    source = pdf_with(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    def fake_require(binary, operation):
        return "gs"

    def fake_run(args, **kwargs):
        staged = Path(args[-2].split("=", 1)[1])
        staged.write_bytes(b"")  # ghostscript "succeeded" but wrote nothing
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(pdfops.deps, "require", fake_require)
    monkeypatch.setattr(pdfops.subprocess, "run", fake_run)

    with pytest.raises(BadInput, match="ghostscript"):
        pdfops.compress(source, out, quality="ebook", reporter=NullReporter(), force=False)

    assert not out.exists()


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


def _stub_ghostscript(monkeypatch, fake_run):
    monkeypatch.setattr(pdfops.deps, "require", lambda binary, operation: "gs")
    monkeypatch.setattr(pdfops.subprocess, "run", fake_run)


def _staged_path(args) -> Path:
    return Path(args[-2].split("=", 1)[1])


def test_compress_rejects_ghostscript_silently_dropping_pages(tmp_path, monkeypatch):
    """Ghostscript's characteristic failure on a damaged PDF is not an empty
    file but a valid, readable, *shorter* one, which every other check passes."""
    source = pdf_with(tmp_path / "in.pdf", 5)
    out = tmp_path / "out.pdf"

    def fake_run(args, **kwargs):
        pdf_with(_staged_path(args), 2)
        return subprocess.CompletedProcess(args, 0)

    _stub_ghostscript(monkeypatch, fake_run)
    with pytest.raises(BadInput, match="dropped pages: 5 in, 2 out"):
        pdfops.compress(source, out, quality="ebook", reporter=NullReporter(), force=False)
    assert not out.exists()


def test_compress_accepts_a_ghostscript_output_with_the_same_page_count(tmp_path, monkeypatch):
    source = pdf_with(tmp_path / "in.pdf", 4)
    out = tmp_path / "out.pdf"

    def fake_run(args, **kwargs):
        pdf_with(_staged_path(args), 4)
        return subprocess.CompletedProcess(args, 0)

    _stub_ghostscript(monkeypatch, fake_run)
    pdfops.compress(source, out, quality="ebook", reporter=NullReporter(), force=False)
    assert page_count(out) == 4


def test_compress_reports_a_ghostscript_failure_with_its_own_message(tmp_path, monkeypatch):
    source = pdf_with(tmp_path / "in.pdf", 2)

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="**** Unable to open the initial device.\n"
        )

    _stub_ghostscript(monkeypatch, fake_run)
    with pytest.raises(BadInput, match="Unable to open the initial device"):
        pdfops.compress(
            source, tmp_path / "out.pdf", quality="ebook", reporter=NullReporter(), force=False
        )


def test_a_failed_compress_leaves_the_existing_destination_intact(tmp_path, monkeypatch):
    """--force clears the way for the write, so the write itself must not be
    able to truncate what is already there."""
    source = pdf_with(tmp_path / "in.pdf", 3)
    out = tmp_path / "out.pdf"
    out.write_bytes(b"%PDF-precious-and-irreplaceable")

    def fake_run(args, **kwargs):
        _staged_path(args).write_bytes(b"%PDF-trunc")  # died part-way through
        return subprocess.CompletedProcess(args, 0)

    _stub_ghostscript(monkeypatch, fake_run)
    with pytest.raises(BadInput):
        pdfops.compress(source, out, quality="ebook", reporter=NullReporter(), force=True)
    assert out.read_bytes() == b"%PDF-precious-and-irreplaceable"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.pdf", "out.pdf"]


def test_every_pdf_operation_writes_through_the_staging_helper(tmp_path, monkeypatch):
    calls = []
    real = pdfops.stage_and_move

    def spy(destination, write):
        calls.append(destination)
        return real(destination, write)

    monkeypatch.setattr(pdfops, "stage_and_move", spy)
    source = pdf_with(tmp_path / "in.pdf", 3)
    pdfops.merge([source], tmp_path / "m.pdf", NullReporter(), force=False)
    pdfops.split(
        source, tmp_path / "s.pdf", pages="1-2", every=None, each=False,
        reporter=NullReporter(), force=False,
    )
    pdfops.rotate(source, tmp_path / "r.pdf", 90, None, NullReporter(), force=False)
    pdfops.extract_pages(source, tmp_path / "p.pdf", "2", NullReporter(), force=False)
    assert [path.name for path in calls] == ["m.pdf", "s.pdf", "r.pdf", "p.pdf"]
