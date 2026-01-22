import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

from gui.core.logging import logs_dir


class DiagnosticsSheet:
    """
    Drawer-like diagnostics panel implemented as the 'sheet' of an Adw.BottomSheet.
    This avoids window-level get_bottom_sheet()/set_bottom_sheet() APIs (not available on some distros).
    """

    def __init__(self, bottom_sheet: Adw.BottomSheet, get_text_cb, save_cb, copy_cb):
        self.sheet_host = bottom_sheet
        self._get_text = get_text_cb
        self._save = save_cb
        self._copy = copy_cb

        self.text = Gtk.TextView(editable=False, monospace=True)
        self.text.set_hexpand(True)
        self.text.set_vexpand(True)
        self.buf = self.text.get_buffer()

        sc = Gtk.ScrolledWindow()
        sc.set_hexpand(True)
        sc.set_vexpand(True)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sc.set_child(self.text)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        btn_copy = Gtk.Button(label="Copy")
        btn_copy.connect("clicked", lambda *_: self._copy())
        header.pack_end(btn_copy)

        btn_save = Gtk.Button(label="Save to file")
        btn_save.connect("clicked", lambda *_: self._save())
        header.pack_end(btn_save)

        btn_folder = Gtk.Button(label="Open folder")
        btn_folder.connect("clicked", lambda *_: self.open_folder())
        header.pack_end(btn_folder)

        # Close button for drawer
        btn_close = Gtk.Button(label="Close")
        btn_close.add_css_class("flat")
        btn_close.connect("clicked", lambda *_: self.sheet_host.set_open(False))
        header.pack_start(btn_close)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        v.append(header)
        v.append(sc)

        # Attach as the sheet content of the BottomSheet
        self.sheet_host.set_sheet(v)
        self.sheet_host.set_can_close(True)

    def open_folder(self):
        path = logs_dir()
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)

    def refresh(self):
        self.buf.set_text(self._get_text() or "")

    def open(self):
        self.refresh()
        self.sheet_host.set_open(True)

    def close(self):
        self.sheet_host.set_open(False)

    def toggle(self):
        if self.sheet_host.get_open():
            self.close()
        else:
            self.open()

