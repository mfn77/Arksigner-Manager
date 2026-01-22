#!/usr/bin/env python3
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime

APP_ID = "tr.org.arksigner.Manager"  # case-sensitive


def _log_path() -> Path:
    base = Path.home() / ".local" / "state" / "arksigner-manager"
    base.mkdir(parents=True, exist_ok=True)
    return base / "gui.log"


def log(msg: str):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def excepthook(exc_type, exc, tb):
    log("UNCAUGHT EXCEPTION:")
    log("".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = excepthook

# Ensure imports work no matter how executed.
# Installed layout: /usr/share/arksigner-manager/gui/app.py
_THIS = Path(__file__).resolve()
_PKGROOT = _THIS.parents[1]  # /usr/share/arksigner-manager
if str(_PKGROOT) not in sys.path:
    sys.path.insert(0, str(_PKGROOT))

log(f"Starting app (APP_ID={APP_ID})")
log(f"sys.path[0]={sys.path[0]}")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
except (ImportError, ValueError) as e:
    # Missing GTK4/libadwaita introspection data or python-gobject bindings.
    msg = (
        "GTK4/libadwaita bindings are not available.\n"
        f"Error: {e}\n\n"
        "On Arch Linux install:\n"
        "  sudo pacman -S gtk4 libadwaita python-gobject gobject-introspection\n\n"
        "On Fedora install:\n"
        "  sudo dnf install gtk4 libadwaita python3-gobject gobject-introspection\n"
    )
    log(msg)
    try:
        sys.stderr.write(msg + "\n")
    except Exception:
        pass
    raise SystemExit(1)

from gi.repository import Adw, Gio  # noqa: E402

from gui.ui.main_window import MainWindow  # noqa: E402


class App(Adw.Application):
    def __init__(self):
        flags = Gio.ApplicationFlags.FLAGS_NONE
        if os.environ.get("ARKSIGNER_MANAGER_NON_UNIQUE", "") == "1":
            flags |= Gio.ApplicationFlags.NON_UNIQUE

        Adw.Application.__init__(self, application_id=APP_ID, flags=flags)
        self._main_window = None

    def do_startup(self):
        log("App do_startup (enter)")
        # Chain up correctly for pygobject overrides:
        Adw.Application.do_startup(self)
        log("App do_startup (after chain-up)")

    def do_activate(self):
        log("App do_activate")
        if self._main_window is None:
            self._main_window = MainWindow(self)
            log("MainWindow created")

        self._main_window.present()
        log("MainWindow presented")


if __name__ == "__main__":
    try:
        app = App()
        rc = app.run(sys.argv)
        log(f"App().run() returned rc={rc}")
    except Exception:
        log("FATAL in App().run():")
        log(traceback.format_exc())
        raise

