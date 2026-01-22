import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class ConfirmPage:
    """
    Right-panel confirmation page for potentially destructive actions.
    """

    def __init__(self, title: str, body: str, confirm_label: str, on_confirm, on_cancel, destructive: bool = True):
        self._title = title
        self._body = body
        self._confirm_label = confirm_label
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._destructive = destructive
        self.page = self._build()

    def _build(self) -> Adw.NavigationPage:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_hexpand(True)
        outer.set_vexpand(True)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        t = Gtk.Label(label=self._title, xalign=0)
        t.add_css_class("title-2")
        outer.append(t)

        b = Gtk.Label(label=self._body, xalign=0)
        b.add_css_class("dim-label")
        b.set_wrap(True)
        outer.append(b)

        spacer = Gtk.Label(label="")
        spacer.set_vexpand(True)
        outer.append(spacer)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.add_css_class("flat")
        btn_cancel.connect("clicked", lambda *_: self._on_cancel())
        bottom.append(btn_cancel)

        grow = Gtk.Label(label="")
        grow.set_hexpand(True)
        bottom.append(grow)

        btn_ok = Gtk.Button(label=self._confirm_label)
        if self._destructive:
            btn_ok.add_css_class("destructive-action")
        else:
            btn_ok.add_css_class("suggested-action")
        btn_ok.connect("clicked", lambda *_: self._on_confirm())
        bottom.append(btn_ok)

        outer.append(bottom)

        return Adw.NavigationPage.new(outer, "Confirm")

