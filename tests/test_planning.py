from pathlib import Path

import pytest

from pdfc.errors import BadInput
from pdfc.formats import Format
from pdfc.planning import Plan, Step, build_plan, check_writable, execute, output_paths
from pdfc.progress import NullReporter
from pdfc.registry import Registry


def test_single_output_uses_the_exact_path(tmp_path):
    assert output_paths(tmp_path / "out.pdf", "in", 1, "pdf") == [tmp_path / "out.pdf"]


def test_multiple_outputs_insert_a_padded_index(tmp_path):
    paths = output_paths(tmp_path / "page.png", "scan", 12, "png")
    assert paths[0].name == "page-001.png"
    assert paths[-1].name == "page-012.png"


def test_padding_widens_past_three_digits(tmp_path):
    paths = output_paths(tmp_path / "page.png", "scan", 1200, "png")
    assert paths[0].name == "page-0001.png"


def test_existing_directory_target_uses_the_input_stem(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    paths = output_paths(out, "scan", 3, "png")
    assert paths[0] == out / "scan-001.png"


def test_extensionless_target_is_treated_as_a_directory(tmp_path):
    # A path that does not exist yet is a directory when it carries no suffix.
    paths = output_paths(tmp_path / "out", "scan", 2, "png")
    assert paths[0].parent.name == "out"
    assert paths[0].name == "scan-001.png"


def test_suffixed_target_is_a_file_even_when_it_does_not_exist(tmp_path):
    paths = output_paths(tmp_path / "out.png", "scan", 2, "png")
    assert paths[0].parent == tmp_path
    assert paths[0].name == "out-001.png"


def test_single_output_into_a_directory_still_uses_the_stem(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert output_paths(out, "scan", 1, "pdf") == [out / "scan.pdf"]


def test_check_writable_rejects_an_existing_file(tmp_path):
    existing = tmp_path / "out.pdf"
    existing.write_text("x")
    with pytest.raises(BadInput, match="already exists"):
        check_writable([existing], force=False)
    check_writable([existing], force=True)


def test_build_plan_stages_every_step_inside_scratch(tmp_path):
    registry = Registry()
    registry.register(Format.MD, Format.HTML, lambda step: None, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, lambda step: None, (), 1, ("converting", "converted"))
    route = registry.route(Format.MD, Format.PDF, lambda _b: True)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    plan = build_plan(route, tmp_path / "in.md", tmp_path / "out.pdf", {}, NullReporter(), scratch)
    assert len(plan.steps) == 2
    assert plan.steps[0].target.parent == scratch
    assert plan.steps[0].target.suffix == ".html"
    assert plan.steps[1].source == plan.steps[0].target
    # The final step writes into staging under the name it will carry at the target.
    assert plan.steps[1].target == scratch / "final" / "out.pdf"
    assert plan.steps[1].destination_hint == tmp_path / "out.pdf"
    assert plan.target == tmp_path / "out.pdf"


def test_plan_describe_lists_every_hop(tmp_path):
    registry = Registry()
    registry.register(Format.MD, Format.HTML, lambda step: None, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, lambda step: None, (), 1, ("converting", "converted"))
    route = registry.route(Format.MD, Format.PDF, lambda _b: True)
    plan = build_plan(route, tmp_path / "in.md", tmp_path / "out.pdf", {}, NullReporter(), tmp_path)
    described = plan.describe()
    assert "md → html" in described and "html → pdf" in described


def test_execute_refuses_to_overwrite_without_force(tmp_path):
    def write(step: Step) -> None:
        step.target.write_text("new")
        step.outputs.append(step.target)

    registry = Registry()
    registry.register(Format.HTML, Format.PDF, write, (), 1, ("converting", "converted"))
    route = registry.route(Format.HTML, Format.PDF, lambda _b: True)
    existing = tmp_path / "out.pdf"
    existing.write_text("old")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    plan = build_plan(route, tmp_path / "in.html", existing, {}, NullReporter(), scratch)
    with pytest.raises(BadInput, match="already exists"):
        execute(plan)
    assert existing.read_text() == "old"
    execute(plan, force=True)
    assert existing.read_text() == "new"


def test_execute_runs_steps_in_order_and_returns_final_outputs(tmp_path):
    calls = []

    def first(step: Step) -> None:
        calls.append("first")
        step.target.write_text("intermediate")
        step.outputs.append(step.target)

    def second(step: Step) -> None:
        calls.append("second")
        step.target.write_text(step.source.read_text() + "-final")
        step.outputs.append(step.target)

    registry = Registry()
    registry.register(Format.MD, Format.HTML, first, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, second, (), 1, ("converting", "converted"))
    route = registry.route(Format.MD, Format.PDF, lambda _b: True)
    out = tmp_path / "out.pdf"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    plan = build_plan(route, tmp_path / "in.md", out, {}, NullReporter(), scratch)
    outputs = execute(plan)
    assert calls == ["first", "second"]
    assert outputs == [out]
    assert out.read_text() == "intermediate-final"


def test_verb_pairs_collects_every_step(tmp_path):
    registry = Registry()
    registry.register(Format.PDF, Format.PNG, lambda s: None, (), 1, ("rendering", "rendered"))
    route = registry.route(Format.PDF, Format.PNG, lambda _b: True)
    plan = build_plan(route, tmp_path / "a.pdf", tmp_path / "b.png", {}, NullReporter(), tmp_path)
    assert plan.verb_pairs == [("rendering", "rendered")]
