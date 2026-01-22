import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class ProgressPage:
    """
    Right-panel progress page.
    Exposes:
      - self.widget : Gtk.Widget
      - reset(title)
      - set_progress(pct, msg)
      - set_text(text)
      - set_busy(busy)
    """

    def __init__(self, on_cancel):
        self.on_cancel = on_cancel
        self._busy = False
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_hexpand(True)
        outer.set_vexpand(True)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        # No title - it's in the headerbar

        self.bar = Gtk.ProgressBar()
        self.bar.set_hexpand(True)
        self.bar.set_show_text(True)
        self.bar.set_fraction(0.0)
        self.bar.set_text("")
        # Disable pulse mode initially
        self.bar.set_pulse_step(0.0)
        outer.append(self.bar)

        self.hint = Gtk.Label(
            label="Authentication may be requested while starting.\nOpen Diagnostics to view detailed output.",
            xalign=0,
        )
        self.hint.add_css_class("dim-label")
        self.hint.set_wrap(True)
        outer.append(self.hint)

        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        row.append(spacer)

        self.btn_cancel = Gtk.Button(label="Cancel")
        self.btn_cancel.connect("clicked", lambda *_: self.on_cancel())
        row.append(self.btn_cancel)

        outer.append(row)
        return outer

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        # Cancel only enabled while busy
        self.btn_cancel.set_sensitive(self._busy)

    def reset(self, title: str):
        # Title goes to headerbar, not here
        self.set_progress(0, "Starting…")
        # Stop any pulse animation
        self.bar.set_pulse_step(0.0)

    def set_text(self, text: str):
        # keep existing fraction; change label only
        self.bar.set_text(text or "")

    def set_progress(self, pct: int, msg: str):
        try:
            pct = int(pct)
        except Exception:
            pct = 0
        pct = max(0, min(100, pct))

        # Stop pulse mode and set actual progress
        self.bar.set_pulse_step(0.0)
        self.bar.set_fraction(pct / 100.0)
        self.bar.set_text(f"{pct}% - {msg}" if msg else f"{pct}%")
