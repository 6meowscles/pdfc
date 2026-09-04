import pytest
from click.testing import CliRunner

from pdfc.cli import main
from pdfc.formats import Format
from pdfc.registry import REGISTRY


def _dummy_pdf_to_txt(step) -> None:
    """Writes fixed text so tests can exercise CLI plumbing (route dispatch,
    stdin/stdout wiring) without depending on a real converter -- Task 9
    leaves pdfc.converters empty, so no such edge exists yet."""
    step.target.write_text("Page 1 of the sample document.")
    step.outputs.append(step.target)


@pytest.fixture
def pdf_to_txt_edge():
    """Temporarily registers a synthetic pdf -> txt edge on the real registry."""
    edge = REGISTRY.register(
        Format.PDF, Format.TXT, _dummy_pdf_to_txt, (), 1, ("extracting", "extracted")
    )
    try:
        yield edge
    finally:
        REGISTRY._edges.remove(edge)


def make_runner() -> CliRunner:
    # click < 8.2 merges stderr into stdout unless asked not to; 8.2 removed the
    # parameter and always keeps them apart.
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


def run(args, **kwargs):
    return make_runner().invoke(main, args, **kwargs)


def test_unknown_first_argument_falls_back_to_convert(sample_md, tmp_path):
    result = run([str(sample_md), str(tmp_path / "out.pdf"), "--dry-run"])
    assert result.exit_code in (0, 2)
    assert "Usage" not in result.stderr


def test_known_subcommand_still_wins(sample_pdf):
    result = run(["routes"])
    assert result.exit_code == 0
    assert "source" in result.stdout.lower()


def test_routes_marks_availability(pdf_to_txt_edge):
    result = run(["routes"])
    assert result.exit_code == 0
    assert "available" in result.stdout or "blocked" in result.stdout


def test_missing_input_file_exits_1(tmp_path):
    result = run([str(tmp_path / "nope.pdf"), str(tmp_path / "out.png")])
    assert result.exit_code == 1
    assert "nope.pdf" in result.stderr


def test_no_route_exits_2(sample_pdf, tmp_path):
    result = run([str(sample_pdf), str(tmp_path / "out.xlsx")])
    assert result.exit_code == 2
    assert "no route" in result.stderr


def test_errors_go_to_stderr_not_stdout(sample_pdf, tmp_path):
    result = run([str(sample_pdf), str(tmp_path / "out.xlsx")])
    assert result.stdout == ""
    assert result.stderr != ""


def test_stdin_requires_a_from_format():
    result = run(["-", "out.pdf"], input="# hi\n")
    assert result.exit_code == 1
    assert "--from" in result.stderr


def test_stdout_target_writes_the_conversion_to_stdout(sample_pdf, pdf_to_txt_edge):
    result = run([str(sample_pdf), "-", "--to", "txt"])
    assert result.exit_code == 0
    assert "Page 1 of the sample document." in result.stdout


def test_stdout_requires_a_to_format(sample_pdf):
    result = run([str(sample_pdf), "-"])
    assert result.exit_code == 1
    assert "--to" in result.stderr


def test_unknown_format_override_exits_1(sample_pdf, tmp_path):
    result = run([str(sample_pdf), str(tmp_path / "out.png"), "--to", "bogus"])
    assert result.exit_code == 1
    assert "unknown format" in result.stderr
