Name:           pdfc
Version:        0.2.0
Release:        1%{?dist}
Summary:        Local PDF converter: images, text, markdown, HTML and office formats

License:        AGPL-3.0-or-later
URL:            https://github.com/6meowscles/pdfc
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pytest
BuildRequires:  python3-pymupdf
BuildRequires:  python3-pillow
BuildRequires:  python3-markdown
BuildRequires:  python3-weasyprint
BuildRequires:  python3-click
BuildRequires:  python3-rich

Requires:       python3-pymupdf
Requires:       python3-pillow
Requires:       python3-markdown
Requires:       python3-weasyprint
Requires:       python3-click
Requires:       python3-rich

# Optional at runtime. pdfc probes for each and prints the dnf command for
# whatever is missing, so none of these are hard requirements.
Recommends:     ghostscript
Suggests:       libreoffice
Suggests:       tesseract
Suggests:       ocrmypdf

%description
pdfc converts documents and images into PDF, out of PDF, and between PDF
files, entirely on the local machine.

Converters register as edges in a graph keyed by format, and routing is a
shortest-path search through PDF as a hub, so a conversion with no direct
converter still works: docx to png routes through PDF with no dedicated code.

It also merges, splits, rotates and compresses PDFs, and OCRs scanned ones.
Tools it does not require but can use -- LibreOffice, tesseract, ghostscript --
are detected at runtime; "pdfc routes" lists every conversion and marks which
are unavailable, with the command to install what is missing.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files pdfc

install -Dpm 0644 README.md %{buildroot}%{_docdir}/%{name}/README.md
install -Dpm 0644 docs/design.md %{buildroot}%{_docdir}/%{name}/design.md

%check
# Conversions needing an absent optional tool skip themselves, so this passes
# in a build root where libreoffice and tesseract are not installed.
%pytest

%files -f %{pyproject_files}
%license LICENSE
%doc %{_docdir}/%{name}/README.md
%doc %{_docdir}/%{name}/design.md
%{_bindir}/pdfc

%changelog
* Sat Sep 05 2026 6meowscles <mharshita2309@gmail.com> - 0.2.0-1
- Install hints now match the running system rather than assuming Arch
* Sat Sep 05 2026 6meowscles <mharshita2309@gmail.com> - 0.1.3-1
- Initial package
