import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class ConfirmActionPage:
    """
    Right-panel confirmation page (non-modal).
    """

    def __init__(self, on_continue, on_cancel):
        self._on_continue = on_continue
        self._on_cancel = on_cancel
        self._action = None
        self._cfg = None
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_hexpand(True)
        outer.set_vexpand(True)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        self.title = Gtk.Label(label="Confirm", xalign=0)
        self.title.add_css_class("title-1")
        self.title.set_wrap(True)
        outer.append(self.title)

        self.body = Gtk.Label(label="", xalign=0)
        self.body.add_css_class("dim-label")
        self.body.set_wrap(True)
        outer.append(self.body)

        self.details = Gtk.Label(label="", xalign=0)
        self.details.add_css_class("caption")
        self.details.set_wrap(True)
        self.details.set_visible(False)
        outer.append(self.details)

        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        self.btn_cancel = Gtk.Button(label="Cancel")
        self.btn_cancel.connect("clicked", lambda *_: self._on_cancel())
        btn_row.append(self.btn_cancel)

        self.btn_continue = Gtk.Button(label="Continue")
        self.btn_continue.add_css_class("suggested-action")
        self.btn_continue.connect("clicked", lambda *_: self._continue())
        btn_row.append(self.btn_continue)

        outer.append(btn_row)
        return outer

    def set_busy(self, busy: bool):
        self.btn_cancel.set_sensitive(not busy)
        self.btn_continue.set_sensitive(not busy)

    def configure(self, action: str, cfg: dict, title: str, body: str, destructive: bool = False, details: str | None = None):
        self._action = action
        self._cfg = cfg

        self.title.set_text(title or "Confirm")
        self.body.set_text(body or "")

        if details:
            self.details.set_text(details)
            self.details.set_visible(True)
        else:
            self.details.set_visible(False)

        self.btn_continue.remove_css_class("destructive-action")
        self.btn_continue.remove_css_class("suggested-action")
        if destructive:
            self.btn_continue.add_css_class("destructive-action")
        else:
            self.btn_continue.add_css_class("suggested-action")

    def _continue(self):
        if not self._action or self._cfg is None:
            return
        self._on_continue(self._action, self._cfg)

