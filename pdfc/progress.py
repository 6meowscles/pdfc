import os
import sys
import time
from collections.abc import Iterable
from typing import TextIO

MIN_VERB_WIDTH = 9


def human_size(byte_count: float) -> str:
    """One rendering of a byte count, so every converter agrees on it."""
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            # Bytes are whole things; a fractional count of them reads oddly.
            return f"{value:.0f} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def verb_width_for(verb_pairs: Iterable[tuple[str, str]]) -> int:
    widths = [len(verb) for pair in verb_pairs for verb in pair]
    return max([MIN_VERB_WIDTH, *widths]) if widths else MIN_VERB_WIDTH


def resolve_mode(mode: str, stream: TextIO) -> str:
    if mode != "auto":
        return mode
    return "bar" if getattr(stream, "isatty", lambda: False)() else "plain"


class Reporter:
    """Reports one step as an -ing verb while it runs and an -ed verb when done."""

    def __init__(self, stream: TextIO | None = None, verb_width: int = MIN_VERB_WIDTH) -> None:
        self.stream = stream if stream is not None else sys.stderr
        self.verb_width = verb_width
        self.verbs: tuple[str, str] = ("", "")
        self.label = ""
        self.started_at = 0.0

    def start(self, verbs: tuple[str, str], label: str, total: int | None) -> None:
        self.verbs = verbs
        self.label = label
        self.started_at = time.monotonic()

    def advance(self, n: int = 1) -> None:
        pass

    def finish(self, summary: str) -> None:
        pass

    def warn(self, message: str) -> None:
        self.stream.write(f"warning: {message}\n")
        self.stream.flush()

    def _elapsed(self) -> str:
        return f"{time.monotonic() - self.started_at:.1f}s"

    def _line(self, verb: str, rest: str) -> str:
        return f"{verb.ljust(self.verb_width)}  {self.label}  {rest}".rstrip()

    def _done_line(self, summary: str) -> str:
        # An internal step reports no destination, so skip the gap it would leave.
        rest = "  ".join(part for part in (summary, self._elapsed()) if part)
        return self._line(self.verbs[1], rest)


class NullReporter(Reporter):
    pass


class PlainReporter(Reporter):
    def start(self, verbs: tuple[str, str], label: str, total: int | None) -> None:
        super().start(verbs, label, total)
        detail = f"{total} pages" if total else ""
        self.stream.write(self._line(verbs[0], detail) + "\n")
        self.stream.flush()

    def finish(self, summary: str) -> None:
        self.stream.write(self._done_line(summary) + "\n")
        self.stream.flush()


class BarReporter(Reporter):
    """Redraws one line with a bar or spinner, then replaces it with the past-tense line."""

    def __init__(self, stream: TextIO | None = None, verb_width: int = MIN_VERB_WIDTH) -> None:
        super().__init__(stream, verb_width)
        self._progress = None
        self._task = None

    def start(self, verbs: tuple[str, str], label: str, total: int | None) -> None:
        super().start(verbs, label, total)
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        console = Console(file=self.stream, no_color=bool(os.environ.get("NO_COLOR")))
        text = TextColumn(f"{verbs[0].ljust(self.verb_width)}  {label}")
        columns = (
            [text, BarColumn(), MofNCompleteColumn(), TimeElapsedColumn()]
            if total
            else [SpinnerColumn(), text, TimeElapsedColumn()]
        )
        self._progress = Progress(*columns, console=console, transient=True)
        self._progress.start()
        self._task = self._progress.add_task("step", total=total)

    def advance(self, n: int = 1) -> None:
        if self._progress is not None and self._task is not None:
            self._progress.advance(self._task, n)

    def finish(self, summary: str) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task = None
        self.stream.write(self._done_line(summary) + "\n")
        self.stream.flush()

    def warn(self, message: str) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
        super().warn(message)


def make_reporter(
    mode: str, verb_width: int = MIN_VERB_WIDTH, stream: TextIO | None = None
) -> Reporter:
    stream = stream if stream is not None else sys.stderr
    resolved = resolve_mode(mode, stream)
    if resolved == "none":
        return NullReporter(stream, verb_width)
    if resolved == "bar":
        return BarReporter(stream, verb_width)
    return PlainReporter(stream, verb_width)
