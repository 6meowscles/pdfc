class Pdfc < Formula
  include Language::Python::Virtualenv

  desc "Local PDF converter: images, text, markdown, HTML and office formats"
  homepage "https://github.com/6meowscles/pdfc"
  url "https://github.com/6meowscles/pdfc/archive/refs/tags/v0.2.2.tar.gz"
  sha256 "PLACEHOLDER_REGENERATE_AFTER_TAGGING"
  license "AGPL-3.0-or-later"
  head "https://github.com/6meowscles/pdfc.git", branch: "main"

  # weasyprint loads pango and cairo at import time, so they are hard requirements.
  depends_on "cairo"
  depends_on "pango"
  depends_on "python@3.13"

  # Optional at runtime. pdfc detects each one and prints the brew command for
  # whatever is missing, so none of these need declaring here:
  #   brew install ghostscript tesseract ocrmypdf
  #   brew install --cask libreoffice

  resource "click" do
    url "https://files.pythonhosted.org/packages/c7/0e/7fa0ef50764b67090eca4114772a2abf8b6148198475e54c660b97caeee6/click-8.5.0.tar.gz"
    sha256 "ba0d2089de75ea0310e2dde03160e6ca10009947fb95a182f9b54021bb272e34"
  end

  resource "Markdown" do
    url "https://files.pythonhosted.org/packages/29/6f/da4c6aea59b3001f2e8c0ec7497475aadaf3b021c10cab5b2858f0f32b26/markdown-3.10.3.tar.gz"
    sha256 "3589362618f743188b4d955b874402bc814f4f83f544dc207719f4baa7d9c45f"
  end

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/1c/3d/bb7fca845737cf9d7dbde16ed1843984665ff2e0a518f5db43e77ec540b9/pillow-12.3.0.tar.gz"
    sha256 "3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce"
  end

  # Builds MuPDF from source, which is by far the slowest part of this install.
  resource "pymupdf" do
    url "https://files.pythonhosted.org/packages/a3/fb/b6761fa2d5266f2cdb24c3b91f4023070ab7848381417678e7a289a1d52a/pymupdf-1.28.2.tar.gz"
    sha256 "5e0be7908a715aa20333caddd73f1d6f01e4cd0c26e869fa2dd0b7f344da2249"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/c0/8f/0722ca900cc807c13a6a0c696dacf35430f72e0ec571c4275d2371fca3e9/rich-15.0.0.tar.gz"
    sha256 "edd07a4824c6b40189fb7ac9bc4c52536e9780fbbfbddf6f1e2502c31b068c36"
  end

  resource "weasyprint" do
    url "https://files.pythonhosted.org/packages/59/53/dcc3885c2f7a47faa45f6b8b801412f5f9e055173a52801ef01c09943c5a/weasyprint-69.0.tar.gz"
    sha256 "a7a32f39ca16bd82ef11de99c92ea4b5f14951c9033af035e451ce4f4ee0a88c"
  end

  # weasyprint's own dependencies, which the virtualenv has to vendor too.
  resource "cffi" do
    url "https://files.pythonhosted.org/packages/9e/ef/008a1939e372c06329a3fce4279c02f328488f3526744906eeec3da7ad5f/cffi-2.1.1.tar.gz"
    sha256 "dd31f52ea1086513bb9df30f8fcee9b8918323ae067a3d5b78bc826a000712be"
  end

  resource "cssselect2" do
    url "https://files.pythonhosted.org/packages/06/00/2456b6b664c7a770989cbe3c352aac4eb962c938486f03a2e1255ae963c6/cssselect2-0.10.1.tar.gz"
    sha256 "83b0d820ef589dabaf693289b647c2f5b410f76d285f56deba911ffa75a7b9d1"
  end

  resource "fonttools" do
    url "https://files.pythonhosted.org/packages/d4/41/0f072a712dc74496e03710e462a18a4cfd8a258ad055a4e22d28b43a7abd/fonttools-4.64.0.tar.gz"
    sha256 "ecb2e59a7bc692fee64dda6010deb66222335693b30046f15cccf81233aa715f"
  end

  resource "pycparser" do
    url "https://files.pythonhosted.org/packages/1b/7d/92392ff7815c21062bea51aa7b87d45576f649f16458d78b7cf94b9ab2e6/pycparser-3.0.tar.gz"
    sha256 "600f49d217304a5902ac3c37e1281c9fe94e4d0489de643a9504c5cdfdfc6b29"
  end

  resource "pyphen" do
    url "https://files.pythonhosted.org/packages/94/47/8430452269cd28863d73b903d07d329d058cf762527ff211b3864ba61fc7/pyphen-0.18.1.tar.gz"
    sha256 "dbae6fbbe4f01cb206108b43573d857c67107be9d0e38eb1b08d6fa2210634a7"
  end

  resource "tinycss2" do
    url "https://files.pythonhosted.org/packages/a3/ae/2ca4913e5c0f09781d75482874c3a95db9105462a92ddd303c7d285d3df2/tinycss2-1.5.1.tar.gz"
    sha256 "d339d2b616ba90ccce58da8495a78f46e55d4d25f9fd71dfd526f07e7d53f957"
  end

  resource "tinyhtml5" do
    url "https://files.pythonhosted.org/packages/b1/1f/cfe2f6b30557c92b3f31d41707e09cef5c1efbd87392bc6c0430c46b0e4d/tinyhtml5-2.1.0.tar.gz"
    sha256 "60a50ec3d938a37e491efa01af895853060943dcebb5627de5b10d188b338a67"
  end

  resource "webencodings" do
    url "https://files.pythonhosted.org/packages/d5/a0/8fd707bcb776a7be556bad06a2ea5fb9bd519df78ef8e26f70ccf0f38bff/webencodings-0.6.1.tar.gz"
    sha256 "565f9ad031c702dae404e27a099e3e09186a3ab1b9520f06d215502b651fd910"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    # A conversion needing no optional tool: markdown reaches PDF through HTML,
    # so this exercises routing, both converters, and the output path.
    (testpath/"notes.md").write("# Heading\n\nA paragraph.\n")
    system bin/"pdfc", "notes.md", "notes.pdf"
    assert_predicate testpath/"notes.pdf", :exist?
    assert_equal "%PDF", (testpath/"notes.pdf").read(4)

    # The conversion graph, and the version the formula claims to have built.
    assert_match "source", shell_output("#{bin}/pdfc routes")
    assert_match version.to_s, shell_output("#{bin}/pdfc --version")
  end
end
