import pytest

from pdfc.errors import BadInput
from pdfc.pages import parse_pages


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("1", [1]),
        ("1-3", [1, 2, 3]),
        ("1-5,9", [1, 2, 3, 4, 5, 9]),
        ("9,1-2", [1, 2, 9]),
        ("1-2,2-3", [1, 2, 3]),
        ("8-", [8, 9, 10]),
        ("-3", [1, 2, 3]),
        (" 1 - 2 , 4 ", [1, 2, 4]),
    ],
)
def test_valid_specs(spec, expected):
    assert parse_pages(spec, page_count=10) == expected


@pytest.mark.parametrize("spec", ["", "0", "11", "3-2", "a", "1--2", "1,,2", "-"])
def test_invalid_specs(spec):
    with pytest.raises(BadInput):
        parse_pages(spec, page_count=10)


def test_out_of_range_message_names_the_page_count():
    with pytest.raises(BadInput, match="only has 10 pages"):
        parse_pages("12", page_count=10)
