import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pdfc.errors import BadInput
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
    destination_hint: Path
    outputs: list[Path] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.edge.label


@dataclass
class Plan:
    steps: list[Step]
    target: Path
    target_is_dir: bool

    @property
    def verb_pairs(self) -> list[tuple[str, str]]:
        return [step.edge.verbs for step in self.steps]

    def describe(self) -> str:
        chain = [self.steps[0].edge.source.value] + [s.edge.target.value for s in self.steps]
        lines = [f"route: {' → '.join(chain)}"]
        for step in self.steps:
            lines.append(f"  {step.edge.label}  {step.source.name} → {step.destination_hint}")
        return "\n".join(lines)


def _is_directory_target(target: Path) -> bool:
    # An existing directory, or a path with no extension, is a directory target.
    # Path() normalises a trailing slash away, so it cannot be used as the signal.
    return target.is_dir() or target.suffix == ""


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


def build_plan(
    route: list[Edge],
    source: Path,
    target: Path,
    options: dict[str, Any],
    reporter: Reporter,
    scratch: Path,
) -> Plan:
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
        hint = target if last else step_target
        steps.append(Step(edge, current, step_target, options, reporter, hint))
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
        shutil.move(str(staged), destination)
    return destinations
