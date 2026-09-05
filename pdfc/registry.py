import importlib
import pkgutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pdfc.errors import MissingDependency, NoRoute
from pdfc.formats import Format

MAX_HOPS = 2

ConverterFunc = Callable[[Any], None]


@dataclass(frozen=True)
class Edge:
    source: Format
    target: Format
    func: ConverterFunc
    requires: tuple[str, ...]
    cost: int
    verbs: tuple[str, str]
    order: int

    @property
    def label(self) -> str:
        return f"{self.source.value} → {self.target.value}"


class Registry:
    def __init__(self) -> None:
        self._edges: list[Edge] = []

    def register(
        self,
        source: Format,
        target: Format,
        func: ConverterFunc,
        requires: Iterable[str] = (),
        cost: int = 1,
        verbs: tuple[str, str] = ("converting", "converted"),
    ) -> Edge:
        edge = Edge(source, target, func, tuple(requires), cost, verbs, len(self._edges))
        self._edges.append(edge)
        return edge

    def edges(self) -> list[Edge]:
        return list(self._edges)

    def _paths(self, source: Format, target: Format) -> list[list[Edge]]:
        """Every path from source to target within MAX_HOPS, no format revisited."""
        found: list[list[Edge]] = []
        stack: list[tuple[Format, list[Edge], set[Format]]] = [(source, [], {source})]
        while stack:
            current, path, seen = stack.pop()
            if len(path) >= MAX_HOPS:
                continue
            for edge in self._edges:
                if edge.source is not current or edge.target in seen:
                    continue
                extended = path + [edge]
                if edge.target is target:
                    found.append(extended)
                else:
                    stack.append((edge.target, extended, seen | {edge.target}))
        return found

    def route(
        self, source: Format, target: Format, available: Callable[[str], bool]
    ) -> list[Edge]:
        if source is target:
            raise NoRoute(source.value, target.value, [f.value for f in self.reachable(source)])

        paths = self._paths(source, target)
        if not paths:
            raise NoRoute(source.value, target.value, [f.value for f in self.reachable(source)])

        def rank(path: list[Edge]) -> tuple[int, int, tuple[int, ...]]:
            return (len(path), sum(e.cost for e in path), tuple(e.order for e in path))

        usable = [p for p in paths if all(available(b) for e in p for b in e.requires)]
        if usable:
            return min(usable, key=rank)

        blocked = min(paths, key=rank)
        for edge in blocked:
            for binary in edge.requires:
                if not available(binary):
                    from pdfc.deps import install_hint

                    raise MissingDependency(binary, install_hint(binary), edge.label)
        raise NoRoute(source.value, target.value, [f.value for f in self.reachable(source)])

    def reachable(self, source: Format) -> set[Format]:
        found: set[Format] = set()
        frontier = {source}
        for _ in range(MAX_HOPS):
            nxt: set[Format] = set()
            for edge in self._edges:
                if edge.source in frontier and edge.target is not source:
                    nxt.add(edge.target)
            found |= nxt
            frontier = nxt
        return found


REGISTRY = Registry()


def converter(
    source: Format,
    target: Format,
    *,
    requires: Iterable[str] = (),
    cost: int = 1,
    verbs: tuple[str, str] = ("converting", "converted"),
) -> Callable[[ConverterFunc], ConverterFunc]:
    def decorate(func: ConverterFunc) -> ConverterFunc:
        REGISTRY.register(source, target, func, requires, cost, verbs)
        return func

    return decorate


_loaded = False


def load_converters() -> None:
    """Import every converter module so its decorators register their edges."""
    global _loaded
    if _loaded:
        return
    import pdfc.converters as package

    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module.name}")
    _loaded = True
