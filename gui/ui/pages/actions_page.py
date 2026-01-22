from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk


class ActionsPage:
    """
    Left sidebar actions list (GNOME Settings style with lighter background).
    Exposes:
      - widget: Gtk.Widget
      - set_busy(busy)
      - save_text_to_file(text)
    """

    def __init__(self, on_action):
        self.on_action = on_action
        self._busy = False
        self._rows = {}  # action -> Gtk.ListBoxRow
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_vexpand(True)
        root.set_hexpand(False)
        root.set_size_request(350, -1)  # Smaller min width

        # GNOME Settings style: lighter sidebar background
        root.add_css_class("sidebar")
        root.add_css_class("view")
        root.add_css_class("background")  # Ensures light background extends everywhere

        # No title inside - it's in the headerbar now
        # title = Gtk.Label(label="Actions", xalign=0)
        # title.add_css_class("title-2")
        # ...
        # root.append(title)

        self.lb = Gtk.ListBox()
        self.lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.lb.add_css_class("navigation-sidebar")
        self.lb.set_margin_top(0)  # No extra margin since title is in headerbar
        self.lb.connect("row-activated", self._on_row_activated)
        root.append(self.lb)

        def add(action: str, title: str, subtitle: str, destructive=False):
            row = Gtk.ListBoxRow()
            row.set_activatable(True)
            row.set_selectable(True)

            h = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            h.set_margin_top(10)
            h.set_margin_bottom(10)
            h.set_margin_start(18)
            h.set_margin_end(18)

            t = Gtk.Label(label=title, xalign=0)
            t.add_css_class("title-4")
            h.append(t)

            s = Gtk.Label(label=subtitle, xalign=0)
            s.add_css_class("dim-label")
            s.add_css_class("caption")
            s.set_wrap(True)
            h.append(s)

            row.set_child(h)

            # store action on row
            row._arks_action = action  # type: ignore[attr-defined]
            row._arks_destructive = destructive  # type: ignore[attr-defined]

            if destructive:
                row.add_css_class("error")

            self._rows[action] = row
            self.lb.append(row)

        add("install", "Install", "Configure options then install")
        add("upgrade", "Upgrade", "Upgrade using the selected mode and package")
        add("repair", "Repair", "Fix mounts/stale units and restart services")
        add("uninstall", "Uninstall", "Remove services and mounts")
        add("purge", "Purge", "Remove everything (including container rootfs)", destructive=True)

        hint_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hint_box.set_margin_top(12)
        hint_box.set_margin_start(18)
        hint_box.set_margin_end(18)
        hint_box.set_margin_bottom(18)

        hint = Gtk.Label(label="Some actions require administrator authentication.", xalign=0)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        hint.set_wrap(True)
        hint_box.append(hint)

        root.append(hint_box)
        return root

    def _on_row_activated(self, _lb, row: Gtk.ListBoxRow):
        if self._busy:
            return
        action = getattr(row, "_arks_action", None)
        if action:
            self.on_action(action)

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        # Disable row activation visually
        for row in self._rows.values():
            row.set_sensitive(not self._busy)

    def save_text_to_file(self, text: str):
        base = Path.home() / ".local" / "state" / "arksigner-manager"
        base.mkdir(parents=True, exist_ok=True)
        fname = base / f"diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        fname.write_text(text or "", encoding="utf-8")
