# pdfc — a local PDF converter CLI

**Date:** 2026-09-05
**Status:** Approved design, ready for implementation planning

## 1. Purpose

A single local command-line tool for converting things into PDF, out of PDF, and
between PDF files. Everything runs on the machine; nothing is uploaded anywhere.

The tool exists because the underlying capabilities are already installed
(poppler, ghostscript, tesseract, ImageMagick) but each has a different,
forgettable invocation. `pdfc` gives them one consistent surface.

### Goals

- One command covers the common conversions in both directions.
- The common case is terse: `pdfc notes.md notes.pdf`.
- Adding a new format later means adding one converter, not editing the CLI.
- Missing optional dependencies produce an actionable message, never a traceback.
- No network access at runtime.

### Non-goals

- A GUI, a daemon, or a watch mode.
- Editing PDF content (annotations, form filling, redaction).
- Perfect fidelity for office formats. LibreOffice's output is the ceiling.
- Publishing to PyPI. This is a personal tool installed from the local checkout.

## 2. CLI surface

The first positional argument decides the mode. If it names a known subcommand,
that subcommand runs; otherwise the arguments are treated as a conversion.

```
pdfc scan.pdf out/page.png --dpi 300     # inferred conversion
pdfc notes.md notes.pdf                  # inferred, routes md -> html -> pdf
pdfc report.docx report.pdf              # inferred, needs libreoffice

pdfc merge a.pdf b.pdf -o all.pdf
pdfc split big.pdf --pages 1-5,9 -o out/
pdfc rotate scan.pdf --angle 90 -o fixed.pdf
pdfc compress big.pdf --quality ebook -o small.pdf
pdfc ocr scan.pdf -o searchable.pdf
pdfc ocr scan.pdf -o text.md --lang eng

pdfc routes                              # print the conversion graph and dep status
```

### Per-command flags

These belong to each subcommand, not to `pdfc` itself, so they follow the
positional arguments rather than preceding them:

```
pdfc notes.md notes.pdf --dry-run    # correct
pdfc --dry-run notes.md notes.pdf    # error: No such option: --dry-run
```

That is a consequence of the inference-first dispatch: an unknown *first*
argument is routed to `convert`, which only works when it is a path or a
subcommand name, so the group itself carries no options beyond `--version`.

| Flag | Meaning | Available on |
|---|---|---|
| `--dry-run` | Print the planned route and output paths; write nothing. | every command |
| `-f, --force` | Overwrite existing outputs. Without it, an existing output is an error. | every command |
| `--progress {auto,bar,plain,none}` | Progress style; `auto` (default) picks `bar` on a TTY and `plain` otherwise. | every command |
| `-q, --quiet` | Equivalent to `--progress none`; errors still print to stderr. | every command |
| `-v, --verbose` | Print each step, the external commands invoked, per-step timings, and full tracebacks on failure. | every command |
| `--from FMT` | Override source format detection (required when input is `-`). | conversions |
| `--to FMT` | Override target format detection. | conversions |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Bad input, unreadable file, or refusing to overwrite |
| 2 | No route exists between the two formats |
| 3 | Route exists but a required external dependency is missing |
| 130 | Interrupted |

## 3. Architecture

Six modules, each usable and testable on its own.

```
pdfc/
  __init__.py
  cli.py            # click group with conversion fallback
  formats.py        # Format enum, extension map, magic-byte sniffing
  registry.py       # converter edges + shortest-path routing
  planning.py       # Plan/Step objects, output path templating
  deps.py           # external binary probing and install hints
  progress.py       # terminal reporting: -ing / -ed step lines
  pages.py          # page-range parsing ("1-5,9,12-")
  errors.py         # typed exceptions -> exit codes
  converters/
    images.py       # pdf <-> raster
    text.py         # pdf <-> txt/md/html
    pdfops.py       # merge, split, rotate, compress, extract
    ocr.py          # tesseract-backed OCR
    office.py       # libreoffice-backed office formats
```

### 3.1 Format detection (`formats.py`)

`Format` is an enum: `PDF, PNG, JPEG, WEBP, TIFF, TXT, MD, HTML, DOCX, ODT,
PPTX, XLSX`.

Detection order for an input path:

1. `--from` if given.
2. Magic bytes, for files that exist (`%PDF`, `\x89PNG`, `PK\x03\x04` + inspect
   the zip's content types for the office formats).
3. Extension.

Output format comes from `--to`, else the output path's extension. If neither
resolves, that is exit code 1 with a message naming both candidates.

Extensions map: `.pdf`, `.png`, `.jpg`/`.jpeg`, `.webp`, `.tif`/`.tiff`,
`.txt`, `.md`/`.markdown`, `.html`/`.htm`, `.docx`, `.odt`, `.pptx`, `.xlsx`.

### 3.2 Registry and routing (`registry.py`)

This is the load-bearing idea. Every converter registers a directed edge:

```python
@converter(source=Format.HTML, target=Format.PDF, requires=(), cost=1)
def html_to_pdf(step: Step) -> None: ...
```

Fields: `source`, `target`, `requires` (tuple of external binary names), `cost`
(lower is preferred when two edges connect the same pair), and the function.

Routing is a breadth-first shortest-path search over the edge set, **capped at
two hops**. PDF is the hub, so `docx -> png` resolves as `docx -> pdf -> png`
with no dedicated code. Edges whose `requires` are unsatisfied are still in the
graph but marked unavailable: if the only route needs a missing binary, the
error is exit code 3 naming it, not exit code 2 claiming the conversion is
impossible.

Candidate paths are ranked by fewest hops first, then lowest total cost, then
declaration order — so a direct edge always beats a chained one, and `cost` only
decides between paths of equal length.

### 3.3 v1 edge table

| Source | Target | Implementation | Requires |
|---|---|---|---|
| PDF | PNG, JPEG, WEBP, TIFF | pymupdf raster render at `--dpi` (default 150) | — |
| PNG, JPEG, WEBP, TIFF | PDF | pillow + pymupdf, one image per page | — |
| PDF | TXT | pymupdf text extraction in reading order | — |
| PDF | MD | pymupdf block extraction; font size relative to page median maps to heading level | — |
| TXT | HTML | wrap in `<pre>` with a minimal stylesheet | — |
| MD | HTML | `markdown` with tables + fenced-code extensions | — |
| HTML | PDF | weasyprint | — |
| DOCX, ODT, PPTX, XLSX | PDF | `libreoffice --headless --convert-to pdf` in a temp profile dir | libreoffice |
| PDF | DOCX | `libreoffice --headless --convert-to docx` | libreoffice |

`md -> pdf` and `txt -> pdf` fall out of routing as two-hop paths through HTML.

**Scanned-input guard:** when a `pdf -> txt`/`pdf -> md` conversion yields under
50 characters per page on average, print a warning pointing at `pdfc ocr`. The
conversion still succeeds; this is advice, not an error.

### 3.4 PDF operations (`converters/pdfops.py`)

These change a PDF without changing its format, so they are subcommands rather
than graph edges.

- **merge** — inputs in argument order, `-o` required. Rejects non-PDF inputs.
- **split** — `--pages 1-5,9` extracts a selection into one PDF; `--every N`
  writes chunks of N pages; `--each` writes one file per page. Exactly one mode
  may be given.
- **rotate** — `--angle {90,180,270,-90}`, optional `--pages` to limit scope.
- **compress** — ghostscript with `-dPDFSETTINGS=/{screen,ebook,printer,prepress}`
  selected by `--quality` (default `ebook`). Prints before/after sizes. If the
  result is larger than the input, keep the original and say so.
- **pages** — extract a range into a new PDF (alias of `split --pages` with a
  single-file output).

### 3.5 OCR (`converters/ocr.py`)

Backed by `ocrmypdf` (pip), which drives tesseract and ghostscript — both
already installed.

- `pdfc ocr in.pdf -o out.pdf` produces a PDF with an invisible text layer.
- `pdfc ocr in.pdf -o out.txt|out.md` OCRs to a temp PDF, then routes through
  the normal `pdf -> txt|md` edge.
- `--lang` defaults to `eng`; validated against `tesseract --list-langs` so a
  missing language pack fails with exit code 3 and the pacman package name.
- `--force-ocr` re-OCRs pages that already carry text.

### 3.6 Dependency probing (`deps.py`)

External binaries are probed once per run and cached: `libreoffice`,
`tesseract`, `gs`. Each has a declared install hint (`sudo pacman -S
libreoffice-fresh`, `tesseract-data-eng`, `ghostscript`). A missing dependency
raises `MissingDependency`, which `cli.py` renders as:

```
error: converting docx -> pdf needs libreoffice
       install it with: sudo pacman -S libreoffice-fresh
```

`pdfc routes` prints the full edge table with each route marked available or
blocked, so the state of the install is inspectable without trial and error.

weasyprint needs pango and cairo at import time; `deps.py` catches that import
error and reports it the same way rather than letting it escape.

### 3.7 Output paths (`planning.py`)

- Single output, target is a file path → written exactly there.
- Multiple outputs (page rendering, `split --each`) and target is a directory —
  an existing directory, or any path with no extension → `<input-stem>-NNN.<ext>`
  inside it. (A trailing `/` cannot be the signal: `Path` normalises it away.)
- Multiple outputs and target is a file path → `-NNN` inserted before the
  extension: `out/page.png` becomes `out/page-001.png`.
- Zero padding is the width of the highest page number, minimum 3.
- Parent directories are created as needed.
- An existing output aborts the whole run before writing anything, unless
  `--force`.

Conversions write to a temp scratch dir and move into place at the end, so a
failure never leaves half-written outputs.

### 3.8 stdin / stdout

`-` as the input reads stdin and requires `--from`. `-` as the output writes to
stdout, permitted only for single-output routes. Both are limited to text
formats and PDF in v1.

### 3.9 Terminal output (`progress.py`)

Every step reports itself twice through one line that rewrites in place: the
present participle while it runs, the past tense when it finishes.

```
$ pdfc scan.pdf out/page.png --dpi 300

  rendering  pdf → png  ████████████░░░░░░  8/12  0:03
  ↓ same line, on completion
  rendered   pdf → png  12 files → out/  4.2 MB  5.1s
```

**Verb table.** Each converter and subcommand declares its verb pair; the
reporter never invents one.

| Operation | In progress | Complete |
|---|---|---|
| PDF → raster | rendering | rendered |
| Any other format change | converting | converted |
| PDF → text/markdown | extracting | extracted |
| merge | merging | merged |
| split / pages | splitting | split |
| rotate | rotating | rotated |
| compress | compressing | compressed |
| ocr | I SEE YOU | I SAW YOU |

Verbs are left-aligned and padded to the width of the widest verb in the run,
so the OCR pair does not misalign the other steps' columns.

The completion line carries what was produced: file count or output name, total
bytes, elapsed time. A multi-step route prints one such line per step, so
`md → html → pdf` leaves two completed lines behind.

**Rules that hold in every mode:**

- All progress goes to **stderr**. `pdfc x.pdf - > out.txt` stays clean.
- `--progress auto` resolves to `bar` only when stderr is a TTY; otherwise
  `plain`, which prints the `-ing` line on start and appends the `-ed` line on
  finish with no ANSI, no redraw, no bar.
- `NO_COLOR` in the environment disables styling but keeps the redraw.
- Steps that cannot report page counts (LibreOffice, ghostscript) show a
  spinner in place of the bar; the verb pair is unchanged.
- `none` prints nothing on success. Warnings and errors always print.
- Under `-v`, the bar is suppressed in favour of plain lines, so the extra
  diagnostic output isn't fighting a redraw for the same terminal row.

The reporter is a small interface (`start(step)`, `advance(n)`, `finish(step,
summary)`) with three implementations — bar, plain, null — so converters call
the same methods regardless of mode and the choice is made once in `cli.py`.
The bar implementation is the only thing that touches `rich`.

## 4. Error handling

`errors.py` defines `PdfcError` and subclasses `BadInput` (1), `NoRoute` (2),
`MissingDependency` (3). `cli.py` catches `PdfcError`, prints
`error: <message>` to stderr, and exits with the mapped code. Any other
exception prints a one-line summary plus "run with -v for the full traceback";
`-v` re-raises.

`NoRoute` lists what *is* reachable from the source format, so a typo'd
extension is immediately obvious.

## 5. Testing

pytest, test-first throughout.

- **Fixtures are generated, not committed.** A session fixture builds a 3-page
  PDF with known text, a 64×64 PNG, and a small markdown file into a tmp dir.
  No binary blobs in git.
- **Routing** is tested against a synthetic registry, independent of any real
  converter, covering: direct edge, two-hop path, hop cap, tie-breaking,
  unavailable-dependency edges, and no-route.
- **Converters** assert structural properties — page count, output dimensions,
  extracted text contains a known sentence, output is a valid PDF header — not
  byte equality, which is unstable across library versions.
- **Path templating** and **page-range parsing** are pure functions with table
  tests, including malformed input.
- **CLI** is exercised through click's `CliRunner`, asserting exit codes and
  stderr text.
- **Progress reporting** is tested through the null and plain reporters against
  a recording fake: that each step emits its `-ing` verb then its `-ed` verb,
  that the verb comes from the operation's declared pair, that `auto` resolves
  to `plain` when stderr is not a TTY, that `none` emits nothing on success but
  still emits warnings, and that nothing reaches stdout. The bar reporter is
  covered only for construction and mode selection — its rendering is rich's
  concern, not ours.
- Tests needing an absent binary are marked (`@pytest.mark.needs_libreoffice`)
  and skipped, so the suite passes on this machine today.

## 6. Install

```
~/Projects/pdfc/          # checkout
  .venv/                  # created by python -m venv
~/.local/bin/pdfc         # shim onto .venv/bin/pdfc
```

Runtime pip dependencies: `click`, `rich`, `pymupdf`, `pillow`, `markdown`,
`weasyprint`, `ocrmypdf`. Dev: `pytest`.

**Known install risk:** the system Python is 3.14.7, which is new enough that
pymupdf, weasyprint, or ocrmypdf may not yet publish wheels for it, forcing
source builds. Phase 1 therefore begins by creating the venv and installing the
dependency set. If a wheel is unavailable, the venv is rebuilt against Python
3.12 (`pacman -S python312`) instead of fighting a source build. This is
verified before any converter is written.

## 7. Build order

Each phase ends with a tool that works and a green test suite.

1. **Skeleton** — package layout, venv, dependency install verified, `errors`,
   `formats`, `registry`, `planning`, `cli` dispatch, `pdfc routes`,
   `--dry-run`. No real conversions; routing is fully tested against synthetic
   edges.
2. **Images ↔ PDF** — the first real edges, pure pip, no external binaries.
3. **Text ↔ PDF** — txt/md/html edges, giving `md -> pdf` via two-hop routing;
   the scanned-input warning.
4. **PDF operations** — merge, split, rotate, compress, pages.
5. **OCR** — ocrmypdf integration, language validation.
6. **Office formats** — libreoffice edges behind the optional-dependency path.

## 8. Deferred

Explicitly out of scope for v1, listed so the design doesn't drift into them:
pandoc-backed routes, EPUB, PDF/A conversion, encryption and password removal,
watermarking, form filling, parallel page rendering, config files, and shell
completions.
