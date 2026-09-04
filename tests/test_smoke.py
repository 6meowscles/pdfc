from click.testing import CliRunner

from pdfc import __version__
from pdfc.cli import main


def test_version_is_set():
    assert __version__ == "0.1.0"


def test_cli_reports_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
