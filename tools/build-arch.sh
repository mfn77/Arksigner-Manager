#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKGDIR="$ROOT/packaging/arch"

echo "==> Building Arch package for arksigner-manager"
echo "    Root: $ROOT"

cd "$ROOT"

# Arch paketini build etmek için makepkg gerekir
if ! command -v makepkg >/dev/null 2>&1; then
  echo "ERROR: makepkg not found. Install base-devel:"
  echo "  sudo pacman -S base-devel"
  exit 1
fi

# Verify structure
if [[ ! -f "$PKGDIR/PKGBUILD" ]]; then
  echo "ERROR: PKGBUILD not found at: $PKGDIR/PKGBUILD"
  exit 1
fi

# Verify critical files exist
need=(
  "backend/arksigner_manager.py"
  "backend/lib/main.py"
  "gui/app.py"
  "gui/ui/main_window.py"
  "assets/tr.org.arksigner.Manager.policy"
  "assets/tr.org.arksigner.Manager.desktop"
)

for f in "${need[@]}"; do
  if [[ ! -f "$ROOT/$f" ]]; then
    echo "ERROR: Required file missing: $f"
    exit 1
  fi
done

# Temizlik
echo "==> Cleaning old packages"
rm -f "$PKGDIR"/*.pkg.tar.* 2>/dev/null || true
rm -f "$PKGDIR"/*.log 2>/dev/null || true
rm -f "$ROOT"/*.pkg.tar.* 2>/dev/null || true
rm -f "$ROOT/PKGBUILD" 2>/dev/null || true

# PKGBUILD'i root'a kopyala (makepkg buradan çalışacak)
echo "==> Copying PKGBUILD to repo root"
cp -f "$PKGDIR/PKGBUILD" "$ROOT/PKGBUILD"

# Derle
echo "==> Building package with makepkg"
makepkg -sf --noconfirm

# Paketi bul
PKG="$(ls -1t "$ROOT"/arksigner-manager-*.pkg.tar.* 2>/dev/null | head -n1)"

if [[ -z "$PKG" || ! -f "$PKG" ]]; then
  echo "ERROR: Package not found after build"
  exit 1
fi

echo "==> Built: $PKG"

# dist/ klasörüne kopyala
DIST="$ROOT/dist"
mkdir -p "$DIST"
cp -f "$PKG" "$DIST/"
echo "==> Copied to: $DIST/$(basename "$PKG")"

# Kurulum sor
read -p "Install package? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "==> Installing package"
  sudo pacman -U --noconfirm "$PKG"
  echo ""
  echo "✓ Installation complete!"
  echo "  Run: arksigner-manager"
else
  echo "==> Skipped installation"
  echo "  To install manually: sudo pacman -U $PKG"
fi

# Temizle
rm -f "$ROOT/PKGBUILD"

echo ""
echo "==> Done!"
