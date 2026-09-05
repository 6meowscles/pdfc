import sys
import tempfile
from pathlib import Path

import click

from pdfc import __version__, deps, formats, planning, progress
from pdfc.errors import PdfcError
from pdfc.formats import Format
from pdfc.registry import REGISTRY, load_converters


class PdfcGroup(click.Group):
    """A group whose unknown first argument is treated as a conversion source."""

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if args and (args[0] == "-" or not args[0].startswith("-")):
                return "convert", self.get_command(ctx, "convert"), args
            raise

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except PdfcError as error:
            click.echo(f"error: {error}", err=True)
            ctx.exit(error.exit_code)


def _format_option(value: str | None) -> Format | None:
    return formats.from_name(value) if value else None


@click.group(cls=PdfcGroup)
@click.version_option(__version__)
def main() -> None:
    """Convert things into PDF, out of PDF, and between PDFs."""


def _common_options(func):
    func = click.option("--dry-run", is_flag=True, help="Print the plan; write nothing.")(func)
    func = click.option("-f", "--force", is_flag=True, help="Overwrite existing outputs.")(func)
    func = click.option(
        "--progress",
        "progress_mode",
        type=click.Choice(["auto", "bar", "plain", "none"]),
        default="auto",
        help="Progress style.",
    )(func)
    func = click.option("-q", "--quiet", is_flag=True, help="Same as --progress none.")(func)
    func = click.option("-v", "--verbose", is_flag=True, help="Show steps and tracebacks.")(func)
    return func


@main.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.argument("target", type=click.Path(path_type=Path))
@click.option("--from", "from_fmt", default=None, help="Override the source format.")
@click.option("--to", "to_fmt", default=None, help="Override the target format.")
@click.option("--dpi", type=int, default=150, show_default=True, help="Raster output density.")
@_common_options
def convert(source, target, from_fmt, to_fmt, dpi, dry_run, force, progress_mode, quiet, verbose):
    """Convert SOURCE into TARGET, inferring the route from their formats."""
    run_conversion(
        source=source,
        target=target,
        from_fmt=from_fmt,
        to_fmt=to_fmt,
        options={"dpi": dpi, "force": force, "verbose": verbose},
        dry_run=dry_run,
        force=force,
        progress_mode="none" if quiet else progress_mode,
        verbose=verbose,
    )


def run_conversion(
    source: Path,
    target: Path,
    from_fmt: str | None,
    to_fmt: str | None,
    options: dict,
    dry_run: bool = False,
    force: bool = False,
    progress_mode: str = "auto",
    verbose: bool = False,
) -> list[Path]:
    load_converters()
    with tempfile.TemporaryDirectory(prefix="pdfc-") as scratch_name:
        scratch = Path(scratch_name)

        if str(source) == "-":
            if not from_fmt:
                raise click.ClickException("reading from stdin needs --from")
            source = scratch / f"stdin.{formats.from_name(from_fmt).value}"
            source.write_bytes(sys.stdin.buffer.read())
        if not source.exists():
            raise click.ClickException(f"cannot read {source}")

        to_stdout = str(target) == "-"
        if to_stdout:
            if not to_fmt:
                raise click.ClickException("writing to stdout needs --to")
            target = scratch / f"stdout.{formats.from_name(to_fmt).value}"

        source_format = formats.detect_input(source, _format_option(from_fmt))
        target_format = formats.detect_output(target, _format_option(to_fmt))
        route = REGISTRY.route(source_format, target_format, deps.have)

        mode = "plain" if verbose and progress_mode in ("auto", "bar") else progress_mode
        width = progress.verb_width_for([edge.verbs for edge in route])
        reporter = progress.make_reporter(mode, width, sys.stderr)

        plan = planning.build_plan(route, source, target, options, reporter, scratch)
        if dry_run:
            click.echo(plan.describe())
            return []
        # Refuse an existing output before doing the work rather than after it.
        # The output count is not always knowable ahead of the run, so execute()
        # still checks what was actually produced.
        predicted = plan.predicted_outputs()
        if predicted is not None:
            planning.check_writable(predicted, force)
        outputs = planning.execute(plan, force=force)

        if to_stdout:
            if len(outputs) != 1:
                raise click.ClickException("writing to stdout needs a single-output conversion")
            sys.stdout.buffer.write(outputs[0].read_bytes())
            return []
        return outputs


@main.command()
def routes() -> None:
    """List every conversion route and whether its dependencies are installed."""
    load_converters()
    click.echo(f"{'source':<8} {'target':<8} {'status':<10} requires")
    for edge in sorted(REGISTRY.edges(), key=lambda e: (e.source.value, e.target.value)):
        blocked = [b for b in edge.requires if not deps.have(b)]
        status = "blocked" if blocked else "available"
        needs = ", ".join(edge.requires) if edge.requires else "-"
        click.echo(f"{edge.source.value:<8} {edge.target.value:<8} {status:<10} {needs}")


from pdfc.converters import pdfops


def _reporter_for(quiet: bool, progress_mode: str, verbose: bool, verbs: tuple[str, str]):
    mode = "none" if quiet else ("plain" if verbose and progress_mode in ("auto", "bar") else progress_mode)
    width = progress.verb_width_for([verbs])
    return progress.make_reporter(mode, width, sys.stderr)


@main.command()
@click.argument("sources", nargs=-1, required=True, type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@_common_options
def merge(sources, output, dry_run, force, progress_mode, quiet, verbose):
    """Concatenate PDFs in the order given."""
    reporter = _reporter_for(quiet, progress_mode, verbose, ("merging", "merged"))
    if dry_run:
        click.echo(f"merge: {len(sources)} files → {output}")
        return
    pdfops.merge(list(sources), output, reporter, force)


@main.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@click.option("--pages", default=None, help='Page selection, e.g. "1-5,9".')
@click.option("--every", type=int, default=None, help="Write chunks of N pages.")
@click.option("--each", is_flag=True, help="Write one file per page.")
@_common_options
def split(source, output, pages, every, each, dry_run, force, progress_mode, quiet, verbose):
    """Split a PDF by selection, by chunk size, or into single pages."""
    reporter = _reporter_for(quiet, progress_mode, verbose, ("splitting", "split"))
    if dry_run:
        click.echo(f"split: {source} → {output}")
        return
    pdfops.split(source, output, pages, every, each, reporter, force)


@main.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@click.option("--angle", type=int, required=True, help="90, 180, 270, or -90.")
@click.option("--pages", default=None, help="Limit rotation to these pages.")
@_common_options
def rotate(source, output, angle, pages, dry_run, force, progress_mode, quiet, verbose):
    """Rotate every page, or the pages named by --pages."""
    reporter = _reporter_for(quiet, progress_mode, verbose, ("rotating", "rotated"))
    if dry_run:
        click.echo(f"rotate: {source} by {angle}° → {output}")
        return
    pdfops.rotate(source, output, angle, pages, reporter, force)


@main.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@click.option(
    "--quality",
    type=click.Choice(pdfops.QUALITIES),
    default="ebook",
    show_default=True,
)
@_common_options
def compress(source, output, quality, dry_run, force, progress_mode, quiet, verbose):
    """Shrink a PDF with ghostscript."""
    reporter = _reporter_for(quiet, progress_mode, verbose, ("compressing", "compressed"))
    if dry_run:
        click.echo(f"compress: {source} at /{quality} → {output}")
        return
    pdfops.compress(source, output, quality, reporter, force)


@main.command("pages")
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@click.option("--pages", "selection", required=True, help='Page selection, e.g. "2-4".')
@_common_options
def pages_command(source, output, selection, dry_run, force, progress_mode, quiet, verbose):
    """Extract a page range into a new PDF."""
    reporter = _reporter_for(quiet, progress_mode, verbose, ("splitting", "split"))
    if dry_run:
        click.echo(f"pages: {selection} of {source} → {output}")
        return
    pdfops.extract_pages(source, output, selection, reporter, force)


@main.command()
@click.argument("source", type=click.Path(path_type=Path))
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path))
@click.option("--lang", default="eng", show_default=True, help="tesseract language code.")
@click.option("--force-ocr", is_flag=True, help="Re-OCR pages that already carry text.")
@_common_options
def ocr(source, output, lang, force_ocr, dry_run, force, progress_mode, quiet, verbose):
    """Recognise text in a scanned PDF."""
    from pdfc.converters import ocr as ocr_module

    reporter = _reporter_for(quiet, progress_mode, verbose, ocr_module.VERBS)
    if dry_run:
        click.echo(f"ocr: {source} in {lang} → {output}")
        return
    ocr_module.run_ocr(source, output, lang, force_ocr, reporter, force)


def _entry() -> int:
    try:
        return main.main(standalone_mode=False) or 0
    except PdfcError as error:
        click.echo(f"error: {error}", err=True)
        return error.exit_code
    except click.ClickException as error:
        click.echo(f"error: {error.format_message()}", err=True)
        return 1
    except click.Abort:
        return 130
    except KeyboardInterrupt:
        return 130
    except Exception:
        if "-v" in sys.argv or "--verbose" in sys.argv:
            raise
        click.echo("error: unexpected failure; run with -v for the full traceback", err=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_entry())
