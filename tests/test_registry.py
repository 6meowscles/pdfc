import pytest

from pdfc.errors import MissingDependency, NoRoute
from pdfc.formats import Format
from pdfc.registry import MAX_HOPS, Registry


def noop(step):
    return None


@pytest.fixture
def registry():
    return Registry()


def always(_binary: str) -> bool:
    return True


def never(_binary: str) -> bool:
    return False


def test_direct_edge_is_a_one_step_route(registry):
    registry.register(Format.HTML, Format.PDF, noop, (), 1, ("converting", "converted"))
    route = registry.route(Format.HTML, Format.PDF, always)
    assert [(e.source, e.target) for e in route] == [(Format.HTML, Format.PDF)]


def test_two_hop_route_is_found(registry):
    registry.register(Format.MD, Format.HTML, noop, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, noop, (), 1, ("converting", "converted"))
    route = registry.route(Format.MD, Format.PDF, always)
    assert [e.target for e in route] == [Format.HTML, Format.PDF]


def test_hop_cap_rejects_three_hop_paths(registry):
    registry.register(Format.MD, Format.HTML, noop, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, noop, (), 1, ("converting", "converted"))
    registry.register(Format.PDF, Format.PNG, noop, (), 1, ("rendering", "rendered"))
    assert MAX_HOPS == 2
    with pytest.raises(NoRoute):
        registry.route(Format.MD, Format.PNG, always)


def test_direct_edge_beats_a_cheaper_two_hop_path(registry):
    registry.register(Format.MD, Format.PDF, noop, (), 10, ("converting", "converted"))
    registry.register(Format.MD, Format.HTML, noop, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, noop, (), 1, ("converting", "converted"))
    route = registry.route(Format.MD, Format.PDF, always)
    assert len(route) == 1


def test_cost_breaks_ties_between_equal_length_paths(registry):
    registry.register(Format.PDF, Format.PNG, noop, (), 5, ("rendering", "rendered"))
    cheap = registry.register(Format.PDF, Format.PNG, noop, (), 1, ("rendering", "rendered"))
    route = registry.route(Format.PDF, Format.PNG, always)
    assert route == [cheap]


def test_declaration_order_breaks_remaining_ties(registry):
    first = registry.register(Format.PDF, Format.TXT, noop, (), 1, ("extracting", "extracted"))
    registry.register(Format.PDF, Format.TXT, noop, (), 1, ("extracting", "extracted"))
    assert registry.route(Format.PDF, Format.TXT, always) == [first]


def test_missing_dependency_beats_no_route(registry):
    registry.register(
        Format.DOCX, Format.PDF, noop, ("libreoffice",), 1, ("converting", "converted")
    )
    with pytest.raises(MissingDependency) as caught:
        registry.route(Format.DOCX, Format.PDF, never)
    assert caught.value.binary == "libreoffice"


def test_available_route_is_preferred_over_a_blocked_one(registry):
    blocked = registry.register(
        Format.PDF, Format.TXT, noop, ("libreoffice",), 1, ("extracting", "extracted")
    )
    free = registry.register(Format.PDF, Format.TXT, noop, (), 2, ("extracting", "extracted"))
    route = registry.route(Format.PDF, Format.TXT, lambda binary: binary != "libreoffice")
    assert route == [free] and blocked not in route


def test_no_edges_at_all_is_no_route(registry):
    with pytest.raises(NoRoute, match="no route from pdf to xlsx"):
        registry.route(Format.PDF, Format.XLSX, always)


def test_reachable_reports_everything_within_the_hop_cap(registry):
    registry.register(Format.MD, Format.HTML, noop, (), 1, ("converting", "converted"))
    registry.register(Format.HTML, Format.PDF, noop, (), 1, ("converting", "converted"))
    assert registry.reachable(Format.MD) == {Format.HTML, Format.PDF}


def test_identity_route_is_rejected(registry):
    with pytest.raises(NoRoute):
        registry.route(Format.PDF, Format.PDF, always)
