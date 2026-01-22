import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk


class PostInstallPage:
    """
    Right-panel post-install page:
      - offers optional Firefox PKCS#11 registration
      - provides Finish to return home
    Exposes:
      - self.widget : Gtk.Widget
      - set_busy(busy)
    """

    def __init__(self, on_done, on_firefox_add):
        self.on_done = on_done
        self.on_firefox_add = on_firefox_add
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

        title = Gtk.Label(label="Installation completed", xalign=0)
        title.add_css_class("title-1")
        outer.append(title)

        body = Gtk.Label(
            label="ArkSigner has been installed.\nYou can optionally register the PKCS#11 module in Firefox.",
            xalign=0,
        )
        body.add_css_class("dim-label")
        body.set_wrap(True)
        outer.append(body)

        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.btn_firefox = Gtk.Button(label="Add to Firefox (optional)")
        self.btn_firefox.add_css_class("suggested-action")
        self.btn_firefox.connect("clicked", lambda *_: (None if self._busy else self.on_firefox_add()))
        outer.append(self.btn_firefox)

        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        row.append(spacer)

        self.btn_done = Gtk.Button(label="Finish")
        self.btn_done.add_css_class("suggested-action")
        self.btn_done.connect("clicked", lambda *_: (None if self._busy else self.on_done()))
        row.append(self.btn_done)

        outer.append(row)
        return outer

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        self.btn_firefox.set_sensitive(not self._busy)
        self.btn_done.set_sensitive(not self._busy)

