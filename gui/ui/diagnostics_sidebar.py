import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio

from gui.core.logging import logs_dir


class DiagnosticsSidebar(Gtk.Box):
    """
    Diagnostics panel for OverlaySplitView sidebar.
    """

    def __init__(self, get_text_cb, save_cb, copy_cb, on_close_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(False)
        self.set_vexpand(True)

        self._get_text = get_text_cb
        self._save = save_cb
        self._copy = copy_cb
        self._on_close = on_close_cb

        # Styling - match left panel
        self.add_css_class("navigation-sidebar")

        # Header with close button and title
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.set_margin_start(12)
        header.set_margin_end(12)

        btn_close = Gtk.Button()
        btn_close.set_icon_name("sidebar-show-symbolic")
        btn_close.add_css_class("flat")
        btn_close.set_tooltip_text("Close Diagnostics")
        btn_close.connect("clicked", lambda *_: self._on_close())
        header.append(btn_close)

        title = Gtk.Label(label="Diagnostics")
        title.add_css_class("title-4")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.CENTER)
        header.append(title)

        # Spacer on right to center title
        spacer_right = Gtk.Box()
        spacer_right.set_size_request(40, -1)  # Match button width
        header.append(spacer_right)

        self.append(header)

        # Text view (no header)
        self.text = Gtk.TextView(editable=False, monospace=True)
        self.text.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text.set_margin_start(6)
        self.text.set_margin_end(6)
        self.text.set_margin_top(6)
        self.text.set_margin_bottom(6)
        self.buf = self.text.get_buffer()

        sc = Gtk.ScrolledWindow()
        sc.set_hexpand(True)
        sc.set_vexpand(True)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sc.set_child(self.text)

        self.append(sc)

        # Action buttons
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)

        btn_copy = Gtk.Button(label="Copy")
        btn_copy.add_css_class("pill")
        btn_copy.connect("clicked", lambda *_: self._copy())
        bottom.append(btn_copy)

        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("pill")
        btn_save.connect("clicked", lambda *_: self._save())
        bottom.append(btn_save)

        grow = Gtk.Label(label="")
        grow.set_hexpand(True)
        bottom.append(grow)

        btn_folder = Gtk.Button(label="Open Folder")
        btn_folder.add_css_class("pill")
        btn_folder.connect("clicked", lambda *_: self._open_folder())
        bottom.append(btn_folder)

        self.append(bottom)

    def _open_folder(self):
        path = logs_dir()
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)

    def refresh(self, text: str):
        self.buf.set_text(text or "")
        # Auto-scroll to bottom
        end_iter = self.buf.get_end_iter()
        self.text.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
