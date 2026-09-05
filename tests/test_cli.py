from click.testing import CliRunner

from pdfc.cli import main


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


def test_routes_marks_availability():
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


def test_stdout_target_writes_the_conversion_to_stdout(sample_pdf):
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


def test_dry_run_prints_the_output_paths_not_just_the_target(sample_pdf, tmp_path):
    result = run([str(sample_pdf), str(tmp_path / "shots" / "page.png"), "--dry-run"])
    assert result.exit_code == 0
    assert "route: pdf → png" in result.stdout
    # sample_pdf has three pages, so three files are planned.
    assert "page-001.png" in result.stdout
    assert "page-003.png" in result.stdout
    assert not (tmp_path / "shots").exists()


def test_dry_run_names_a_directory_target_after_the_input(sample_md, tmp_path):
    result = run([str(sample_md), str(tmp_path / "outdir"), "--to", "pdf", "--dry-run"])
    assert result.exit_code == 0
    assert str(tmp_path / "outdir" / "sample.pdf") in result.stdout


def test_dry_run_falls_back_to_the_target_when_the_count_is_unknowable(sample_md, tmp_path):
    # md -> html -> png would need the intermediate PDF to count its pages.
    result = run([str(sample_md), str(tmp_path / "out.html"), "--dry-run"])
    assert result.exit_code == 0
    assert str(tmp_path / "out.html") in result.stdout


def test_existing_output_is_refused_before_the_conversion_runs(sample_md, tmp_path):
    target = tmp_path / "out.pdf"
    target.write_text("previous output")
    result = run([str(sample_md), str(target)])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert target.read_text() == "previous output"


def test_directory_target_names_the_output_after_the_input(sample_md, tmp_path):
    outdir = tmp_path / "outdir"
    result = run([str(sample_md), str(outdir), "--to", "pdf"])
    assert result.exit_code == 0, result.stderr
    assert (outdir / "sample.pdf").exists()
    assert not (outdir / "step0.pdf").exists()


def test_extensionless_target_that_is_a_file_exits_1(sample_md, tmp_path):
    blocker = tmp_path / "Makefile"
    blocker.write_text("all:\n")
    result = run([str(sample_md), str(blocker), "--to", "pdf"])
    assert result.exit_code == 1
    assert "exists and is not a directory" in result.stderr
    assert blocker.read_text() == "all:\n"


def test_a_stdout_run_does_not_print_its_scratch_path(sample_pdf):
    result = run([str(sample_pdf), "-", "--to", "txt", "--progress", "plain"])
    assert result.exit_code == 0
    assert "pdfc-" not in result.stderr
    assert "stdout.txt" not in result.stderr
