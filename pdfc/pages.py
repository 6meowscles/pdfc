from pdfc.errors import BadInput


def parse_pages(spec: str, page_count: int) -> list[int]:
    """Parse a 1-indexed page selection like "1-5,9,12-" into a sorted page list."""
    if not spec or not spec.strip():
        raise BadInput("empty page range")

    selected: set[int] = set()
    for chunk in spec.split(","):
        piece = chunk.strip()
        if not piece:
            raise BadInput(f"empty range in {spec!r}")
        selected.update(_parse_chunk(piece, spec, page_count))
    return sorted(selected)


def _parse_chunk(piece: str, spec: str, page_count: int) -> range:
    if "-" not in piece:
        page = _parse_number(piece, spec, page_count)
        return range(page, page + 1)

    left, separator, right = piece.partition("-")
    if separator and "-" in right:
        raise BadInput(f"malformed range {piece!r} in {spec!r}")

    start = _parse_number(left.strip(), spec, page_count) if left.strip() else 1
    end = _parse_number(right.strip(), spec, page_count) if right.strip() else page_count
    if not left.strip() and not right.strip():
        raise BadInput(f"malformed range {piece!r} in {spec!r}")
    if start > end:
        raise BadInput(f"range {piece!r} runs backwards")
    return range(start, end + 1)


def _parse_number(text: str, spec: str, page_count: int) -> int:
    try:
        value = int(text)
    except ValueError:
        raise BadInput(f"{text!r} in {spec!r} is not a page number") from None
    if value < 1:
        raise BadInput(f"page numbers start at 1, got {value}")
    if value > page_count:
        raise BadInput(f"page {value} requested but the document only has {page_count} pages")
    return value
