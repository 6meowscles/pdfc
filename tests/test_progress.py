import io

import pytest

from pdfc import progress


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


def test_verb_width_uses_the_longest_verb():
    assert progress.verb_width_for([("rendering", "rendered")]) == 9
    assert progress.verb_width_for([("I SEE YOU", "I SAW YOU"), ("merging", "merged")]) == 9
    assert progress.verb_width_for([("compressing", "compressed")]) == 11


def test_resolve_mode_auto_picks_bar_on_a_tty():
    assert progress.resolve_mode("auto", FakeTTY()) == "bar"
    assert progress.resolve_mode("auto", io.StringIO()) == "plain"


def test_resolve_mode_passes_explicit_modes_through():
    for mode in ("bar", "plain", "none"):
        assert progress.resolve_mode(mode, FakeTTY()) == mode


def test_make_reporter_returns_the_right_class():
    assert isinstance(progress.make_reporter("none"), progress.NullReporter)
    assert isinstance(progress.make_reporter("plain", stream=io.StringIO()), progress.PlainReporter)
    assert isinstance(progress.make_reporter("bar", stream=FakeTTY()), progress.BarReporter)


def test_plain_reporter_emits_the_ing_verb_then_the_ed_verb():
    stream = io.StringIO()
    reporter = progress.PlainReporter(stream, verb_width=9)
    reporter.start(("rendering", "rendered"), "pdf → png", total=12)
    reporter.advance(12)
    reporter.finish("12 files → out/  4.2 MB")
    output = stream.getvalue()
    assert "rendering" in output
    assert "rendered" in output
    assert "pdf → png" in output
    assert "12 files → out/" in output
    assert output.index("rendering") < output.index("rendered")


def test_plain_reporter_pads_verbs_to_the_declared_width():
    stream = io.StringIO()
    reporter = progress.PlainReporter(stream, verb_width=9)
    reporter.start(("merging", "merged"), "pdf → pdf", None)
    reporter.finish("all.pdf")
    for line in stream.getvalue().splitlines():
        assert line.startswith("merging  ") or line.startswith("merged   ")


def test_ocr_verbs_pass_through_verbatim():
    stream = io.StringIO()
    reporter = progress.PlainReporter(stream, verb_width=9)
    reporter.start(("I SEE YOU", "I SAW YOU"), "scan.pdf", None)
    reporter.finish("out.pdf")
    output = stream.getvalue()
    assert "I SEE YOU" in output and "I SAW YOU" in output


def test_null_reporter_prints_nothing_on_success_but_still_warns():
    stream = io.StringIO()
    reporter = progress.NullReporter(stream)
    reporter.start(("rendering", "rendered"), "pdf → png", 3)
    reporter.advance(3)
    reporter.finish("done")
    assert stream.getvalue() == ""
    reporter.warn("looks scanned")
    assert "looks scanned" in stream.getvalue()


def test_warnings_are_prefixed():
    stream = io.StringIO()
    progress.PlainReporter(stream, verb_width=9).warn("looks scanned")
    assert stream.getvalue().startswith("warning: ")


def test_bar_reporter_writes_to_its_stream_and_survives_a_full_cycle():
    stream = FakeTTY()
    reporter = progress.BarReporter(stream, verb_width=9)
    reporter.start(("rendering", "rendered"), "pdf → png", total=2)
    reporter.advance(1)
    reporter.advance(1)
    reporter.finish("2 files")
    output = stream.getvalue()
    assert "rendered" in output


def test_nothing_ever_reaches_stdout(capsys):
    stream = io.StringIO()
    reporter = progress.PlainReporter(stream, verb_width=9)
    reporter.start(("merging", "merged"), "pdf → pdf", None)
    reporter.finish("all.pdf")
    reporter.warn("careful")
    captured = capsys.readouterr()
    assert captured.out == ""
