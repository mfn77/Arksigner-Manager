#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPECPATH="$ROOT/packaging/fedora/arksigner-manager.spec"

echo "==> Building Fedora RPM using container (on Arch)"
echo "    Root: $ROOT"

NO_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-install) NO_INSTALL=1 ;;
    *) ;;
  esac
done

# Check if podman or docker available
CONTAINER=""
if command -v podman >/dev/null 2>&1; then
  CONTAINER="podman"
elif command -v docker >/dev/null 2>&1; then
  CONTAINER="docker"
else
  echo "ERROR: Neither podman nor docker found."
  echo "Install one: sudo pacman -S podman"
  exit 1
fi

echo "    Using: $CONTAINER"

# Structure check
need=(
  "$ROOT/backend/arksigner_manager.py"
  "$ROOT/backend/lib/main.py"
  "$ROOT/gui/app.py"
  "$ROOT/gui/ui/main_window.py"
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

VER="$(awk '/^Version:/ {print $2; exit}' "$SPECPATH")"
NAME="$(awk '/^Name:/ {print $2; exit}' "$SPECPATH")"

if [[ -z "$VER" || -z "$NAME" ]]; then
  echo "ERROR: Could not parse Name or Version from spec file"
  exit 1
fi

echo "    Name: $NAME"
echo "    Version: $VER"

DIST="$ROOT/dist"
mkdir -p "$DIST"

# Create tarball
echo "==> Creating source tarball"
TOPDIR="${NAME}-${VER}"
TARBALL="${DIST}/${TOPDIR}.tar.gz"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/$TOPDIR"

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

# Build in Fedora container
echo "==> Building RPM in Fedora container"

$CONTAINER run --rm \
  -v "$DIST:/dist:Z" \
  -v "$SPECPATH:/tmp/arksigner-manager.spec:ro,Z" \
  -w /root \
  fedora:latest \
  bash -c "
    set -ex
    dnf install -y rpm-build rpmdevtools rsync python3 >/dev/null
    rpmdev-setuptree
    
    cp /dist/${TOPDIR}.tar.gz ~/rpmbuild/SOURCES/
    cp /tmp/arksigner-manager.spec ~/rpmbuild/SPECS/
    
    rpmbuild -ba ~/rpmbuild/SPECS/arksigner-manager.spec
    
    cp ~/rpmbuild/RPMS/noarch/*.rpm /dist/
    echo 'Build complete'
  "

RPMFILE="$(ls -1t "$DIST"/*.rpm 2>/dev/null | head -n1)"

if [[ -z "$RPMFILE" || ! -f "$RPMFILE" ]]; then
  echo "ERROR: RPM package not found after build"
  exit 1
fi

echo "==> Built: $RPMFILE"

if [[ "$NO_INSTALL" -eq 1 ]]; then
  echo "==> Skipped installation (--no-install)"
  echo "    RPM available at: $RPMFILE"
  exit 0
fi

echo ""
echo "==> RPM built successfully!"
echo "    Location: $RPMFILE"
echo ""
echo "To install on Fedora:"
echo "    sudo dnf install $RPMFILE"
echo ""
echo "Note: Cannot install RPM on Arch Linux (use PKGBUILD instead)"
