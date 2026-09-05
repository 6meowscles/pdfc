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
