"""Exercises the installed console script directly, in a real subprocess.

`click.testing.CliRunner` (used throughout tests/test_cli.py) invokes
`main.main(...)` in-process and never calls `pdfc.cli:_entry`, the function
`pyproject.toml` actually wires up as the `pdfc` console script. Task 9
shipped a version of `_entry` that exited 0 for every error while the whole
suite still passed, because nothing ran the real entry point. These tests
close that gap by running the installed script (or the module, as a
fallback) as a subprocess and asserting on its actual process exit code.
"""

import subprocess
import sys
from pathlib import Path


def _pdfc_command() -> list[str]:
    """The real console-script entry point, `pdfc.cli:_entry`, invoked as a subprocess."""
    script = Path(sys.executable).with_name("pdfc")
    if script.exists():
        return [str(script)]
    # Fallback for environments where the console script isn't alongside
    # this interpreter: `python -m pdfc.cli` runs the same `_entry()`.
    return [sys.executable, "-m", "pdfc.cli"]


def run(args, **kwargs):
    return subprocess.run([*_pdfc_command(), *args], capture_output=True, text=True, **kwargs)


def test_no_route_exits_2_on_the_real_entry_point(tmp_path):
    import pymupdf

    source = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(source)
    doc.close()

    result = run([str(source), str(tmp_path / "out.xlsx")])
    assert result.returncode == 2
    assert "no route" in result.stderr


def test_missing_input_file_exits_1_on_the_real_entry_point(tmp_path):
    result = run([str(tmp_path / "nope.pdf"), str(tmp_path / "out.png")])
    assert result.returncode == 1
    assert "nope.pdf" in result.stderr


def test_success_exits_0_on_the_real_entry_point():
    result = run(["--version"])
    assert result.returncode == 0


def test_non_ascii_text_survives_an_ascii_locale(tmp_path):
    """The HTML pdfc writes declares utf-8, so its text I/O must not follow the
    platform default encoding. Run the real entry point under the C locale,
    where that default is ANSI_X3.4-1968, and check the bytes match the
    declaration instead of blowing up on the first accented character."""
    import os

    source = tmp_path / "resume.md"
    source.write_text("# Résumé\n\nCafé — naïve façade.\n", encoding="utf-8")
    target = tmp_path / "out.html"
    environment = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }
    result = run([str(source), str(target)], env=environment)
    assert result.returncode == 0, result.stderr
    assert "Café — naïve façade.".encode() in target.read_bytes()


def test_extensionless_target_that_is_a_file_is_a_typed_error(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# hi\n")
    blocker = tmp_path / "Makefile"
    blocker.write_text("all:\n")
    result = run([str(source), str(blocker), "--to", "pdf"])
    assert result.returncode == 1
    assert "exists and is not a directory" in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert blocker.read_text() == "all:\n"
