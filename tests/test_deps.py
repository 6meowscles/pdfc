import pytest

from pdfc import deps
from pdfc.errors import MissingDependency


@pytest.fixture(autouse=True)
def clear_cache():
    deps.reset_cache()
    yield
    deps.reset_cache()


def test_hints_cover_the_optional_binaries():
    assert "libreoffice-fresh" in deps.install_hint("libreoffice")
    assert "tesseract" in deps.install_hint("tesseract")
    assert "ghostscript" in deps.install_hint("gs")


def test_unknown_binary_still_gets_a_hint():
    assert deps.install_hint("frobnicator") == "install frobnicator"


def test_have_is_true_for_a_binary_that_exists():
    assert deps.have("sh") is True


def test_have_is_false_for_nonsense():
    assert deps.have("definitely-not-a-real-binary") is False


def test_have_is_cached(monkeypatch):
    calls = []

    def fake_which(name):
        calls.append(name)
        return "/usr/bin/sh"

    monkeypatch.setattr(deps.shutil, "which", fake_which)
    deps.have("sh")
    deps.have("sh")
    assert calls == ["sh"]


def test_require_returns_the_path_when_present():
    assert deps.require("sh", "test op").endswith("sh")


def test_require_raises_with_the_operation_and_hint():
    with pytest.raises(MissingDependency) as caught:
        deps.require("libreoffice-not-here", "docx → pdf")
    assert "docx → pdf" in str(caught.value)
