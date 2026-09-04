import click

from pdfc import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Convert things into PDF, out of PDF, and between PDFs."""


if __name__ == "__main__":
    main()
