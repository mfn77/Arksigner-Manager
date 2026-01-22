#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPECPATH="$ROOT/packaging/fedora/arksigner-manager.spec"

echo "==> Building Fedora RPM for arksigner-manager"
echo "    Root: $ROOT"

NO_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-install) NO_INSTALL=1 ;;
    *) ;;
  esac
done

# Structure check
need=(
  "$ROOT/backend/arksigner_manager.py"
  "$ROOT/backend/lib/main.py"
  "$ROOT/backend/lib/util.py"
  "$ROOT/backend/lib/container_mode.py"
  "$ROOT/backend/lib/native_mode.py"
  "$ROOT/gui/app.py"
  "$ROOT/gui/ui/main_window.py"
  "$ROOT/gui/ui/pages/actions_page.py"
  "$ROOT/gui/ui/pages/install_setup_page.py"
  "$ROOT/gui/core/privileged.py"
  "$ROOT/assets/tr.org.arksigner.Manager.policy"
  "$ROOT/assets/tr.org.arksigner.Manager.desktop"
  "$SPECPATH"
)

echo "==> Verifying file structure"
for f in "${need[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing file: $f"
    exit 1
  fi
done

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "ERROR: rpmbuild not found. Install rpm-build:"
  echo "  sudo dnf install rpm-build rpmdevtools"
  exit 1
fi

echo "==> Setting up RPM build environment"
RPMTOP="${HOME}/rpmbuild"
mkdir -p "$RPMTOP"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

VER="$(awk '/^Version:/ {print $2; exit}' "$SPECPATH")"
NAME="$(awk '/^Name:/ {print $2; exit}' "$SPECPATH")"
TOPDIR="${NAME}-${VER}"

if [[ -z "$VER" || -z "$NAME" ]]; then
  echo "ERROR: Could not parse Name or Version from spec file"
  exit 1
fi

echo "    Name: $NAME"
echo "    Version: $VER"

TARBALL="$RPMTOP/SOURCES/${TOPDIR}.tar.gz"

echo "==> Creating source tarball"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/$TOPDIR"

# Build tarball (exclude typical junk)
rsync -a \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '*.pkg.tar.*' \
  --exclude '*.rpm' \
  --exclude 'rpmbuild' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '._*' \
  --exclude 'PKGBUILD' \
  "$ROOT/" "$tmp/$TOPDIR/"

tar -czf "$TARBALL" -C "$tmp" "$TOPDIR"
echo "    Created: $TARBALL"

echo "==> Copying spec file"
cp -f "$SPECPATH" "$RPMTOP/SPECS/"

# Build RPM
echo "==> Building RPM package"
rpmbuild -ba "$RPMTOP/SPECS/arksigner-manager.spec"

RPMFILE="$(ls -1t "$RPMTOP/RPMS/noarch/${NAME}-"*.rpm 2>/dev/null | head -n1)"

if [[ -z "$RPMFILE" || ! -f "$RPMFILE" ]]; then
  echo "ERROR: RPM package not found after build"
  exit 1
fi

echo "==> Built: $RPMFILE"

# Copy to repo dist/
DIST="$ROOT/dist"
mkdir -p "$DIST"
cp -f "$RPMFILE" "$DIST/"
echo "==> Copied to: $DIST/$(basename "$RPMFILE")"

if [[ "$NO_INSTALL" -eq 1 ]]; then
  echo "==> Skipped installation (--no-install)"
  echo "    To install manually: sudo dnf install $RPMFILE"
  exit 0
fi

# Install RPM
read -p "Install RPM? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "==> Installing RPM"
  sudo dnf -y install "$RPMFILE"
  echo ""
  echo "✓ Installation complete!"
  echo "  Run: arksigner-manager"
else
  echo "==> Skipped installation"
  echo "    To install manually: sudo dnf install $RPMFILE"
fi

echo ""
echo "==> Done!"
