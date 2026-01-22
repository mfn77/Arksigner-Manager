import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class UpgradePage:
    """
    Upgrade configuration page with mode detection.
    Shows options based on current installation mode.
    """

    def __init__(self, on_confirm):
        self.on_confirm = on_confirm
        self._busy = False
        self._current_mode = None  # Will be detected
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_hexpand(True)
        outer.set_vexpand(True)

        sc = Gtk.ScrolledWindow()
        sc.set_hexpand(True)
        sc.set_vexpand(True)
        sc.set_has_frame(False)
        outer.append(sc)

        page = Adw.PreferencesPage()
        sc.set_child(page)

        # Container upgrade options
        self.grp_container = Adw.PreferencesGroup(
            title="Container Mode",
            description="Upgrade ArkSigner running in systemd-nspawn container",
        )
        page.add(self.grp_container)

        self.row_debian = Adw.ActionRow(
            title="Update Debian base",
            subtitle="Update the container's Debian system packages",
        )
        self.sw_debian = Gtk.Switch()
        self.sw_debian.set_valign(Gtk.Align.CENTER)
        self.row_debian.add_suffix(self.sw_debian)
        self.row_debian.set_activatable_widget(self.sw_debian)
        self.grp_container.add(self.row_debian)

        self.row_arksigner_deb = Adw.ActionRow(
            title="Update ArkSigner .deb",
            subtitle="Download and install latest arksigner-pub .deb package",
        )
        self.sw_arksigner_deb = Gtk.Switch()
        self.sw_arksigner_deb.set_valign(Gtk.Align.CENTER)
        self.sw_arksigner_deb.set_active(True)  # Default: update ArkSigner
        self.row_arksigner_deb.add_suffix(self.sw_arksigner_deb)
        self.row_arksigner_deb.set_activatable_widget(self.sw_arksigner_deb)
        self.grp_container.add(self.row_arksigner_deb)

        self.row_deb_url = Adw.EntryRow(
            title=".deb URL (optional)",
            text=""
        )
        # Add placeholder hint
        # Note: Adw.EntryRow doesn't have set_placeholder_text, so we use title + subtitle
        self.row_deb_url.set_title(".deb URL (optional)")
        self.row_deb_url.set_show_apply_button(False)
        self.grp_container.add(self.row_deb_url)

        hint_container = Adw.ActionRow(
            title="",
            subtitle="Leave empty to automatically find the latest version",
        )
        hint_container.set_activatable(False)
        hint_container.add_css_class("dim-label")
        self.grp_container.add(hint_container)

        # Native upgrade options
        self.grp_native = Adw.PreferencesGroup(
            title="Native Mode",
            description="Upgrade ArkSigner installed natively under /opt",
        )
        page.add(self.grp_native)

        self.row_native_deb = Adw.EntryRow(
            title=".deb URL (optional)",
            text=""
        )
        self.row_native_deb.set_show_apply_button(False)
        self.grp_native.add(self.row_native_deb)

        hint_native = Adw.ActionRow(
            title="",
            subtitle="Leave empty to automatically find the latest version",
        )
        hint_native.set_activatable(False)
        hint_native.add_css_class("dim-label")
        self.grp_native.add(hint_native)

        self.row_rpath = Adw.ActionRow(
            title="Apply RPATH fix (optional)",
            subtitle="Set RPATH to $ORIGIN/libs using patchelf",
        )
        self.sw_rpath = Gtk.Switch()
        self.sw_rpath.set_valign(Gtk.Align.CENTER)
        self.row_rpath.add_suffix(self.sw_rpath)
        self.row_rpath.set_activatable_widget(self.sw_rpath)
        self.grp_native.add(self.row_rpath)

        # Bottom actions
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(12)
        bottom.set_margin_bottom(12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda *_: self.on_confirm(None))
        bottom.append(btn_cancel)

        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        bottom.append(spacer)

        self.btn_upgrade = Gtk.Button(label="Upgrade")
        self.btn_upgrade.add_css_class("suggested-action")
        self.btn_upgrade.connect("clicked", lambda *_: (None if self._busy else self.on_confirm(self.get_cfg())))
        bottom.append(self.btn_upgrade)

        outer.append(bottom)
        return outer

    def set_mode(self, mode: str):
        """Set current installation mode and adjust UI"""
        self._current_mode = mode

        if mode == "container":
            self.grp_container.set_sensitive(True)
            self.grp_native.set_sensitive(False)
        elif mode == "native":
            self.grp_container.set_sensitive(False)
            self.grp_native.set_sensitive(True)
        else:
            # Unknown - enable both
            self.grp_container.set_sensitive(True)
            self.grp_native.set_sensitive(True)

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        self.grp_container.set_sensitive(not self._busy and self._current_mode != "native")
        self.grp_native.set_sensitive(not self._busy and self._current_mode != "container")
        self.btn_upgrade.set_sensitive(not self._busy)

    def get_cfg(self) -> dict:
        if self._current_mode == "container":
            deb_url = self.row_deb_url.get_text().strip()
            return {
                "mode": "container",
                "update_debian": self.sw_debian.get_active(),
                "update_arksigner": self.sw_arksigner_deb.get_active(),
                "deb": deb_url if deb_url else "auto",  # "auto" signals backend to find latest
            }
        elif self._current_mode == "native":
            deb_url = self.row_native_deb.get_text().strip()
            return {
                "mode": "native",
                "deb": deb_url if deb_url else "auto",  # "auto" signals backend to find latest
                "native_rpath": self.sw_rpath.get_active(),
            }
        else:
            return {"mode": "unknown"}
