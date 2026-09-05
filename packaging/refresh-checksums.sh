#!/bin/sh
# Fill in the source checksums once the release tag exists on GitHub.
#
# The archive GitHub serves is built from the tag, so its checksum cannot be
# known until the tag is pushed. Recipes therefore carry a placeholder between
# the version bump and the tag; this script replaces it.
#
#   git tag -a v0.2.2 -m 'pdfc 0.2.2' && git push origin v0.2.2
#   ./packaging/refresh-checksums.sh 0.2.2
set -eu
v="${1:?usage: refresh-checksums.sh VERSION}"
url="https://github.com/6meowscles/pdfc/archive/refs/tags/v$v.tar.gz"

sum=$(curl -fsSL "$url" | sha256sum | cut -d' ' -f1)
[ -n "$sum" ] || { echo "could not fetch $url" >&2; exit 1; }
echo "v$v -> $sum"

cd "$(dirname "$0")/.."
sed -i "s|^sha256sums=(.*)|sha256sums=('$sum')|"            packaging/aur/PKGBUILD
sed -i "s|^\tsha256sums = .*|\tsha256sums = $sum|"          packaging/aur/.SRCINFO
sed -i "s|^  sha256 \".*\"|  sha256 \"$sum\"|"              packaging/homebrew/pdfc.rb

grep -n "$sum" packaging/aur/PKGBUILD packaging/aur/.SRCINFO packaging/homebrew/pdfc.rb
