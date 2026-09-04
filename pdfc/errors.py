from collections.abc import Iterable


class PdfcError(Exception):
    """Base for every error pdfc reports without a traceback."""

    exit_code = 1


class BadInput(PdfcError):
    exit_code = 1


class NoRoute(PdfcError):
    exit_code = 2

    def __init__(self, source: str, target: str, reachable: Iterable[str]) -> None:
        options = ", ".join(sorted(reachable))
        detail = options if options else "nothing"
        super().__init__(
            f"no route from {source} to {target}; "
            f"from {source} you can reach: {detail}"
        )


class MissingDependency(PdfcError):
    exit_code = 3

    def __init__(self, binary: str, hint: str, operation: str) -> None:
        self.binary = binary
        self.hint = hint
        super().__init__(
            f"converting {operation} needs {binary}\n"
            f"       install it with: {hint}"
        )
