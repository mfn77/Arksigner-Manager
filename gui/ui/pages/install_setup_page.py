import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class InstallSetupPage:
    """
    Right-panel install configuration (no title - it's in headerbar).
    Exposes:
      - self.widget : Gtk.Widget
      - get_cfg()   : dict
      - set_busy()  : disable controls while running
    """

    def __init__(self, on_confirm):
        self.on_confirm = on_confirm
        self._busy = False
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_hexpand(True)
        outer.set_vexpand(True)

        # No title section - it's in the headerbar

        sc = Gtk.ScrolledWindow()
        sc.set_hexpand(True)
        sc.set_vexpand(True)
        sc.set_has_frame(False)
        outer.append(sc)

        page = Adw.PreferencesPage()
        sc.set_child(page)

        grp_cfg = Adw.PreferencesGroup(
            title="Configuration",
            description="Choose container or native mode. Container mode is typically most robust.",
        )
        page.add(grp_cfg)

        self.row_mode = Adw.ComboRow(title="Mode")
        self.row_mode.set_model(Gtk.StringList.new(["container", "native"]))
        self.row_mode.set_selected(0)
        grp_cfg.add(self.row_mode)

        self.row_machine = Adw.EntryRow(title="Machine (container)")
        self.row_machine.set_text("debian-arksigner")
        grp_cfg.add(self.row_machine)

        self.row_suite = Adw.EntryRow(title="Debian suite (container)")
        self.row_suite.set_text("bullseye")
        grp_cfg.add(self.row_suite)

        self.row_deb = Adw.EntryRow(title=".deb URL / path")
        self.row_deb.set_text("https://downloads.arksigner.com/files/arksigner-pub-2.3.12.deb")
        grp_cfg.add(self.row_deb)

        grp_opt = Adw.PreferencesGroup(title="Options")
        page.add(grp_opt)

        self.row_recreate = Adw.ActionRow(
            title="Recreate Debian rootfs (container only)",
            subtitle="Use if you suspect a broken rootfs or want a clean reinstall.",
        )
        self.sw_recreate = Gtk.Switch()
        self.sw_recreate.set_valign(Gtk.Align.CENTER)
        self.row_recreate.add_suffix(self.sw_recreate)
        self.row_recreate.set_activatable_widget(self.sw_recreate)
        grp_opt.add(self.row_recreate)

        self.row_rpath = Adw.ActionRow(
            title="Advanced (native): set RPATH to $ORIGIN/libs (opt-in)",
            subtitle="Uses patchelf. Only affects native mode.",
        )
        self.sw_rpath = Gtk.Switch()
        self.sw_rpath.set_valign(Gtk.Align.CENTER)
        self.row_rpath.add_suffix(self.sw_rpath)
        self.row_rpath.set_activatable_widget(self.sw_rpath)
        grp_opt.add(self.row_rpath)

        self.row_mode.connect("notify::selected", lambda *_: self._on_mode_changed())
        self._on_mode_changed()

        # Bottom actions (Install button)
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(12)
        bottom.set_margin_bottom(12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)

        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        bottom.append(spacer)

        self.btn_install = Gtk.Button(label="Install")
        self.btn_install.add_css_class("suggested-action")
        self.btn_install.connect("clicked", lambda *_: (None if self._busy else self.on_confirm(self.get_cfg())))
        bottom.append(self.btn_install)

        outer.append(bottom)
        return outer

    def _mode_value(self) -> str:
        model = self.row_mode.get_model()
        idx = self.row_mode.get_selected()
        if model and 0 <= idx < model.get_n_items():
            return model.get_string(idx)
        return "container"

    def _on_mode_changed(self):
        mode = self._mode_value()
        container = (mode == "container")
        self.row_machine.set_visible(container)
        self.row_suite.set_visible(container)
        self.row_recreate.set_visible(container)
        self.row_rpath.set_visible(not container)

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        self.row_mode.set_sensitive(not self._busy)
        self.row_machine.set_sensitive(not self._busy)
        self.row_suite.set_sensitive(not self._busy)
        self.row_deb.set_sensitive(not self._busy)
        self.sw_recreate.set_sensitive(not self._busy)
        self.sw_rpath.set_sensitive(not self._busy)
        self.btn_install.set_sensitive(not self._busy)

    def get_cfg(self) -> dict:
        mode = self._mode_value()
        machine = (self.row_machine.get_text().strip() or "debian-arksigner")
        suite = (self.row_suite.get_text().strip() or "bullseye")
        deb = (self.row_deb.get_text().strip() or "https://downloads.arksigner.com/files/arksigner-pub-2.3.12.deb")
        recreate = self.sw_recreate.get_active()
        native_rpath = self.sw_rpath.get_active()
        return {
            "mode": mode,
            "machine": machine,
            "suite": suite,
            "deb": deb,
            "recreate": recreate,
            "native_rpath": native_rpath,
        }
