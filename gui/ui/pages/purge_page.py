import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class PurgePage:
    """
    Purge confirmation page with warnings.
    """

    def __init__(self, on_confirm, on_cancel):
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._detected_mode = None
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

        # Detection info
        grp_detect = Adw.PreferencesGroup(
            title="Detected Installation",
        )
        page.add(grp_detect)

        self.row_detected = Adw.ActionRow(
            title="Detected Mode",
            subtitle="Detecting...",
        )
        self.lbl_service = Gtk.Label(label="")
        self.lbl_service.add_css_class("dim-label")
        self.lbl_service.add_css_class("caption")
        self.row_detected.add_suffix(self.lbl_service)
        grp_detect.add(self.row_detected)

        # What will be deleted
        grp_delete = Adw.PreferencesGroup(
            title="This will permanently delete:",
        )
        page.add(grp_delete)

        row1 = Adw.ActionRow(
            title="All services and mounts",
            subtitle="systemd services and bind mounts"
        )
        row1.set_activatable(False)
        icon1 = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        row1.add_prefix(icon1)
        grp_delete.add(row1)

        self.row2 = Adw.ActionRow(
            title="Container rootfs",
            subtitle="/var/lib/machines/debian-arksigner"
        )
        self.row2.set_activatable(False)
        icon2 = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        self.row2.add_prefix(icon2)
        grp_delete.add(self.row2)

        self.row3 = Adw.ActionRow(
            title="/opt/arksigner directory",
            subtitle="All native installation files"
        )
        self.row3.set_activatable(False)
        icon3 = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        self.row3.add_prefix(icon3)
        grp_delete.add(self.row3)

        row4 = Adw.ActionRow(
            title="ALL ArkSigner data",
            subtitle="This cannot be recovered"
        )
        row4.set_activatable(False)
        icon4 = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        row4.add_prefix(icon4)
        grp_delete.add(row4)

        # Advanced options
        grp_advanced = Adw.PreferencesGroup(title="Advanced Options")
        page.add(grp_advanced)

        self.row_override = Adw.ComboRow(title="Mode Override")
        self.row_override.set_subtitle("Change only if auto-detection is wrong")
        self.row_override.set_model(Gtk.StringList.new(["Auto (recommended)", "container", "native"]))
        self.row_override.set_selected(0)
        grp_advanced.add(self.row_override)

        # Confirmation checkbox
        grp_confirm = Adw.PreferencesGroup(title="Confirmation Required")
        page.add(grp_confirm)

        self.row_confirm = Adw.ActionRow(
            title="I understand this will delete everything permanently",
            subtitle="Check this box to enable the Purge button",
        )
        self.sw_confirm = Gtk.Switch()
        self.sw_confirm.set_valign(Gtk.Align.CENTER)
        self.sw_confirm.connect("notify::active", self._on_confirm_toggled)
        self.row_confirm.add_suffix(self.sw_confirm)
        self.row_confirm.set_activatable_widget(self.sw_confirm)
        grp_confirm.add(self.row_confirm)

        # Bottom actions
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(12)
        bottom.set_margin_bottom(12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda *_: self._on_cancel())
        bottom.append(btn_cancel)

        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        bottom.append(spacer)

        self.btn_purge = Gtk.Button(label="Purge Everything")
        self.btn_purge.add_css_class("destructive-action")
        self.btn_purge.set_sensitive(False)  # Disabled until checkbox
        self.btn_purge.connect("clicked", lambda *_: self._confirm())
        bottom.append(self.btn_purge)

        outer.append(bottom)
        return outer

    def _on_confirm_toggled(self, switch, param):
        self.btn_purge.set_sensitive(switch.get_active())

    def detect_mode(self):
        """Detect current installation mode and update UI"""
        try:
            # Check container mode
            p = subprocess.run(
                ["systemctl", "is-active", "arksigner-nspawn.service"],
                capture_output=True,
                text=True
            )
            if p.returncode == 0:
                self._detected_mode = "container"
                self.row_detected.set_subtitle("Container Mode")
                self.lbl_service.set_text("arksigner-nspawn.service")
                # Show container-specific deletion
                self.row2.set_visible(True)
                self.row3.set_visible(False)
                return

            # Check native mode
            p2 = subprocess.run(
                ["systemctl", "is-active", "arksigner-native.service"],
                capture_output=True,
                text=True
            )
            if p2.returncode == 0:
                self._detected_mode = "native"
                self.row_detected.set_subtitle("Native Mode")
                self.lbl_service.set_text("arksigner-native.service")
                # Show native-specific deletion
                self.row2.set_visible(False)
                self.row3.set_visible(True)
                return

            # Not found
            self._detected_mode = "unknown"
            self.row_detected.set_subtitle("No active installation found")
            self.lbl_service.set_text("No service detected")
            self.row2.set_visible(True)
            self.row3.set_visible(True)

        except Exception as e:
            self._detected_mode = "unknown"
            self.row_detected.set_subtitle("Detection failed")
            self.lbl_service.set_text(str(e))
            self.row2.set_visible(True)
            self.row3.set_visible(True)

    def _confirm(self):
        # Get mode (either detected or overridden)
        override_idx = self.row_override.get_selected()
        if override_idx == 0:  # Auto
            mode = self._detected_mode or "container"
        elif override_idx == 1:  # container
            mode = "container"
        else:  # native
            mode = "native"

        cfg = {"mode": mode}
        self._on_confirm(cfg)

    def set_busy(self, busy: bool):
        self.btn_purge.set_sensitive(not busy and self.sw_confirm.get_active())
        self.row_override.set_sensitive(not busy)
        self.sw_confirm.set_sensitive(not busy)

    def reset(self):
        """Reset confirmation checkbox when page is shown"""
        self.sw_confirm.set_active(False)
        self.btn_purge.set_sensitive(False)
