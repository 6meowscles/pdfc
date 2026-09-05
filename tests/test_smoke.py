from click.testing import CliRunner

from pdfc import __version__
from pdfc.cli import main


def test_version_is_set():
    # The exact number moves with releases; what matters is that it exists
    # and is a real version string.
    assert __version__.count(".") == 2
    assert all(part.isdigit() for part in __version__.split("."))


def test_cli_reports_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
