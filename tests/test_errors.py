import pytest

from pdfc.errors import BadInput, MissingDependency, NoRoute, PdfcError


def test_exit_codes():
    assert BadInput("x").exit_code == 1
    assert NoRoute("pdf", "xlsx", []).exit_code == 2
    assert MissingDependency("libreoffice", "sudo pacman -S libreoffice-fresh", "docx -> pdf").exit_code == 3


def test_all_errors_share_a_base():
    for error in (BadInput("x"), NoRoute("a", "b", []), MissingDependency("gs", "hint", "op")):
        assert isinstance(error, PdfcError)


def test_missing_dependency_message_names_binary_and_hint():
    error = MissingDependency("libreoffice", "sudo pacman -S libreoffice-fresh", "docx -> pdf")
    message = str(error)
    assert "docx -> pdf needs libreoffice" in message
    assert "sudo pacman -S libreoffice-fresh" in message


def test_no_route_message_lists_reachable_formats():
    error = NoRoute("pdf", "xlsx", ["png", "txt"])
    message = str(error)
    assert "no route from pdf to xlsx" in message
    assert "png" in message and "txt" in message


def test_no_route_with_nothing_reachable():
    assert "nothing" in str(NoRoute("xlsx", "pptx", []))


def test_bad_input_keeps_its_message():
    with pytest.raises(PdfcError, match="cannot read"):
        raise BadInput("cannot read /nope.pdf")
