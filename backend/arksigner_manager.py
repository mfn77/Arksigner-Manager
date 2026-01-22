#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure imports work when executed directly.
# When installed, this file lives at:
#   /usr/share/arksigner-manager/backend/arksigner_manager.py
# We want /usr/share/arksigner-manager on sys.path so "backend.lib" resolves.
_THIS = Path(__file__).resolve()
_PKGROOT = _THIS.parents[1]  # repo root in dev; /usr/share/arksigner-manager in install

if str(_PKGROOT) not in sys.path:
    sys.path.insert(0, str(_PKGROOT))

from backend.lib.main import main  # noqa: E402

if __name__ == "__main__":
    main()

