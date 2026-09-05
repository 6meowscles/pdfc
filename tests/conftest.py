from pathlib import Path

import pymupdf
import pytest
from PIL import Image


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    for number in range(1, 4):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {number} of the sample document.", fontsize=12)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    path = tmp_path / "sample.png"
    Image.new("RGB", (64, 64), (220, 40, 40)).save(path)
    return path


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text("# Heading\n\nA paragraph of body text.\n")
    return path
