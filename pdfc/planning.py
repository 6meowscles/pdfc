import os
import shutil
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pdfc.errors import BadInput
from pdfc.formats import RASTER, Format
from pdfc.progress import Reporter
from pdfc.registry import Edge

MIN_PAD = 3


@dataclass
class Step:
    edge: Edge
    source: Path
    target: Path
    options: dict[str, Any]
    reporter: Reporter
    destination_hint: Path | str
    origin: Path
    outputs: list[Path] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.edge.label

    def summary(self, *parts: str) -> str:
        """Join the destination with the step's details, dropping the
        destination for an internal step whose path the user never named."""
        return "  ".join(part for part in (str(self.destination_hint), *parts) if part)


@dataclass
class Plan:
    steps: list[Step]
    target: Path
    target_is_dir: bool

    @property
    def verb_pairs(self) -> list[tuple[str, str]]:
        return [step.edge.verbs for step in self.steps]

    def predicted_outputs(self) -> list[Path] | None:
        """The files this plan will write, when they can be known without
        running it, else None. Only a page-per-file step is hard to predict,
        and then only when its own input does not exist yet."""
        last = self.steps[-1]
        extension = last.edge.target.value
        if last.edge.target not in RASTER:
            return output_paths(self.target, last.origin.stem, 1, extension)
        count = _page_count(last.source) if last.edge.source is Format.PDF else None
        if count is None:
            return None
        return output_paths(self.target, last.origin.stem, count, extension)

    def describe(self) -> str:
        chain = [self.steps[0].edge.source.value] + [s.edge.target.value for s in self.steps]
        lines = [f"route: {' → '.join(chain)}"]
        for step in self.steps:
            lines.append(f"  {step.edge.label}  {step.source.name}")
        lines.append("outputs:")
        for path in self.predicted_outputs() or [self.target]:
            lines.append(f"  {path}")
        return "\n".join(lines)


def _page_count(path: Path) -> int | None:
    """The page count of an existing PDF, or None when that cannot be read."""
    try:
        import pymupdf

        with pymupdf.open(path) as doc:
            return doc.page_count
    except Exception:
        return None


def _is_directory_target(target: Path) -> bool:
    # An existing path is a directory target only if it really is a directory;
    # a path that does not exist yet is one when it carries no extension.
    # Path() normalises a trailing slash away, so it cannot be used as the signal.
    if target.exists():
        return target.is_dir()
    return target.suffix == ""


def check_target(target: Path) -> None:
    """Reject a suffix-less target that already exists as something other than a
    directory, which would otherwise only surface as a mkdir() traceback."""
    if target.suffix == "" and target.exists() and not target.is_dir():
        raise BadInput(f"{target} exists and is not a directory")


def output_paths(target: Path, stem: str, count: int, extension: str) -> list[Path]:
    """Expand a user-supplied target into the concrete files a step will write."""
    suffix = extension if extension.startswith(".") else f".{extension}"
    if _is_directory_target(target):
        directory, base = target, stem
    else:
        directory, base = target.parent, target.stem
    if count == 1:
        return [directory / f"{base}{suffix}"]
    pad = max(MIN_PAD, len(str(count)))
    return [directory / f"{base}-{index:0{pad}d}{suffix}" for index in range(1, count + 1)]


def check_writable(paths: Iterable[Path], force: bool) -> None:
    if force:
        return
    for path in paths:
        if path.exists():
            raise BadInput(f"{path} already exists; pass --force to overwrite")


def stage_and_move(destination: Path, write: Callable[[Path], None]) -> Path:
    """Run `write` against a temp path and rename the result into place.

    A failure or interrupt part-way through therefore never leaves a truncated
    file where a valid one used to be. The temp file is a sibling of the
    destination, so the rename is an atomic same-filesystem operation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}.pdfc-"))
    try:
        staged = scratch / destination.name
        write(staged)
        os.replace(staged, destination)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return destination


def build_plan(
    route: list[Edge],
    source: Path,
    target: Path,
    options: dict[str, Any],
    reporter: Reporter,
    scratch: Path,
) -> Plan:
    check_target(target)
    staging = scratch / "final"
    staging.mkdir(parents=True, exist_ok=True)
    target_is_dir = _is_directory_target(target)
    # The final step writes into staging under the name it will carry at the
    # target, so output_paths() templates identically in both places.
    staged_target = staging if target_is_dir else staging / target.name

    steps: list[Step] = []
    current = source
    for index, edge in enumerate(route):
        last = index == len(route) - 1
        step_target = staged_target if last else scratch / f"step{index}.{edge.target.value}"
        # Intermediate files live in a scratch dir the user never named, so only
        # the final step has a destination worth printing.
        hint: Path | str = target if last else ""
        steps.append(Step(edge, current, step_target, options, reporter, hint, source))
        current = step_target
    return Plan(steps, target, target_is_dir)


def execute(plan: Plan, force: bool = False) -> list[Path]:
    # Run every step, then move the staged results into place, so a failure
    # part-way through never leaves half-written outputs at the target.
    for step in plan.steps:
        step.target.parent.mkdir(parents=True, exist_ok=True)
        # Clear outputs before (re-)running: execute() may be called again on the
        # same plan (e.g. a rejected run retried with force=True), and a step's
        # func would otherwise re-append onto whatever it recorded last time.
        step.outputs.clear()
        step.edge.func(step)

    produced = plan.steps[-1].outputs
    directory = plan.target if plan.target_is_dir else plan.target.parent
    destinations = [directory / path.name for path in produced]
    check_writable(destinations, force)
    directory.mkdir(parents=True, exist_ok=True)
    for staged, destination in zip(produced, destinations, strict=True):
        # The scratch directory can be a different filesystem from the
        # destination (e.g. a tmpfs /tmp vs. a real disk $HOME), so plain
        # shutil.move can fall back to copying straight over an existing
        # destination file. Route through stage_and_move instead, so this
        # last hop gets the same stage-beside-destination-then-os.replace
        # guarantee as every other write in this module.
        stage_and_move(destination, lambda dest_staged, source=staged: shutil.copyfile(source, dest_staged))
    return destinations
