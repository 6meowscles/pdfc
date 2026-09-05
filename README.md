# pdfc

A local PDF converter. Everything runs on this machine; nothing is uploaded.

## Install

    ./install.sh

That creates `.venv/`, installs the package, and links `~/.local/bin/pdfc`.
If a dependency has no wheel for your Python, rerun with an older one:
`PYTHON=python3.12 ./install.sh`.

## Use

    pdfc scan.pdf out/page.png --dpi 300   # render pages to images
    pdfc notes.md notes.pdf                # markdown to PDF, via HTML
    pdfc report.docx report.pdf            # needs libreoffice
    pdfc scan.pdf notes.txt                # extract text

    pdfc merge a.pdf b.pdf -o all.pdf
    pdfc split big.pdf --pages 1-5,9 -o out/
    pdfc split big.pdf --each -o pages/
    pdfc rotate scan.pdf --angle 90 -o fixed.pdf
    pdfc compress big.pdf --quality ebook -o small.pdf
    pdfc ocr scan.pdf -o searchable.pdf

`pdfc routes` lists every conversion and whether its dependencies are installed.

`--dry-run`, `-f/--force`, `--progress`, `-q` and `-v` belong to each command
rather than to `pdfc` itself, so they follow the positional arguments:

    pdfc notes.md notes.pdf --dry-run     # prints the route and the output paths
    pdfc split big.pdf --each -o pages/ -f

## Optional dependencies

| Feature | Needs | Install |
|---|---|---|
| Office formats | libreoffice | `sudo pacman -S libreoffice-fresh` |
| OCR | tesseract | `sudo pacman -S tesseract tesseract-data-eng` |
| Compression, OCR | ghostscript | `sudo pacman -S ghostscript` |

## Progress output

Each step prints its verb while it runs and again, past tense, when it finishes:

    rendering  pdf → png  ████████░░░░  8/12  0:03
    rendered   pdf → png  12 files → out/  4.2 MB  5.1s

Progress goes to stderr, so piping stdout stays clean. `--progress
bar|plain|none` overrides the default, which is a bar on a terminal and plain
lines everywhere else.

## Design

`docs/design.md` covers the architecture: the converter registry, the
two-hop routing rule, format detection, output-path templating, and the
error/exit-code contract.

## Tests

    .venv/bin/pytest
