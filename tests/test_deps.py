import pytest

from pdfc import deps
from pdfc.errors import MissingDependency


@pytest.fixture(autouse=True)
def clear_cache():
    deps.reset_cache()
    yield
    deps.reset_cache()


def force_family(monkeypatch, family):
    """Pin the packaging family, so a hint test asserts the same thing on any machine."""
    deps.reset_cache()
    monkeypatch.setattr(deps, "detect_family", lambda: family)


def test_hints_cover_the_optional_binaries(monkeypatch):
    force_family(monkeypatch, "arch")
    assert "libreoffice-fresh" in deps.install_hint("libreoffice")
    assert "tesseract" in deps.install_hint("tesseract")
    assert "ghostscript" in deps.install_hint("gs")


@pytest.mark.parametrize(
    "family,binary,expected",
    [
        ("arch", "gs", "sudo pacman -S ghostscript"),
        ("debian", "gs", "sudo apt install ghostscript"),
        ("fedora", "gs", "sudo dnf install ghostscript"),
        ("suse", "gs", "sudo zypper install ghostscript"),
        ("brew", "gs", "brew install ghostscript"),
        ("debian", "tesseract", "sudo apt install tesseract-ocr"),
        ("debian", "pango", "sudo apt install libpango-1.0-0 libcairo2"),
        ("brew", "libreoffice", "brew install --cask libreoffice"),
    ],
)
def test_each_family_gets_its_own_command(monkeypatch, family, binary, expected):
    force_family(monkeypatch, family)
    assert deps.install_hint(binary) == expected


def test_ocrmypdf_on_arch_points_at_the_aur_not_pacman(monkeypatch):
    force_family(monkeypatch, "arch")
    hint = deps.install_hint("ocrmypdf")
    assert "paru" in hint and "AUR" in hint
    assert "pacman" not in hint


def test_ocrmypdf_elsewhere_is_an_ordinary_package(monkeypatch):
    force_family(monkeypatch, "fedora")
    assert deps.install_hint("ocrmypdf") == "sudo dnf install ocrmypdf"


@pytest.mark.parametrize(
    "family,expected",
    [
        ("arch", "sudo pacman -S tesseract-data-deu"),
        ("debian", "sudo apt install tesseract-ocr-deu"),
        ("fedora", "sudo dnf install tesseract-langpack-deu"),
        ("brew", "brew install tesseract-lang"),
    ],
)
def test_language_packs_are_named_per_family(monkeypatch, family, expected):
    force_family(monkeypatch, family)
    assert deps.language_pack_hint("deu") == expected


def test_an_unrecognised_system_gives_a_generic_hint(monkeypatch):
    force_family(monkeypatch, None)
    assert deps.install_hint("gs") == "install gs"
    assert "tesseract training data" in deps.language_pack_hint("deu")


def test_unknown_binary_still_gets_a_hint():
    assert deps.install_hint("frobnicator") == "install frobnicator"


def test_macos_is_brew(monkeypatch):
    deps.reset_cache()
    monkeypatch.setattr(deps.sys, "platform", "darwin")
    assert deps.detect_family() == "brew"


@pytest.mark.parametrize(
    "os_release,expected",
    [
        ('ID=fedora\nVERSION_ID=41\n', "fedora"),
        ('ID=ubuntu\nID_LIKE=debian\n', "debian"),
        ('ID=cachyos\nID_LIKE="arch"\n', "arch"),
        # An unknown distribution that declares what it is compatible with.
        ('ID=someothething\nID_LIKE="rhel fedora"\n', "fedora"),
        ('ID=plan9\n', None),
        ("", None),
    ],
)
def test_family_is_read_from_os_release(monkeypatch, tmp_path, os_release, expected):
    deps.reset_cache()
    monkeypatch.setattr(deps.sys, "platform", "linux")
    path = tmp_path / "os-release"
    path.write_text(os_release)
    read = deps._read_os_release_ids  # capture before patching, or the patch recurses
    monkeypatch.setattr(deps, "_read_os_release_ids", lambda: read(path))
    assert deps.detect_family() == expected


def test_a_missing_os_release_is_not_an_error(monkeypatch, tmp_path):
    assert deps._read_os_release_ids(tmp_path / "nope") == []


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
