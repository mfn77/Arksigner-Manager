import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class UninstallPage:
    """
    Uninstall confirmation page with automatic mode detection.
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
            description="Automatically detected the current installation mode",
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

        # What will be done
        grp_actions = Adw.PreferencesGroup(
            title="This will:",
            description="",
        )
        page.add(grp_actions)

        row1 = Adw.ActionRow(title="Stop services", subtitle="")
        row1.set_activatable(False)
        icon1 = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        row1.add_prefix(icon1)
        grp_actions.add(row1)

        row2 = Adw.ActionRow(title="Remove mounts", subtitle="")
        row2.set_activatable(False)
        icon2 = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        row2.add_prefix(icon2)
        grp_actions.add(row2)

        row3 = Adw.ActionRow(
            title="Keep container rootfs and /opt files",
            subtitle="Use Purge to remove everything"
        )
        row3.set_activatable(False)
        icon3 = Gtk.Image.new_from_icon_name("emblem-important-symbolic")
        row3.add_prefix(icon3)
        grp_actions.add(row3)

        # Advanced options (expander)
        grp_advanced = Adw.PreferencesGroup(title="Advanced Options")
        page.add(grp_advanced)

        self.row_override = Adw.ComboRow(title="Mode Override")
        self.row_override.set_subtitle("Change only if auto-detection is wrong")
        self.row_override.set_model(Gtk.StringList.new(["Auto (recommended)", "container", "native"]))
        self.row_override.set_selected(0)
        grp_advanced.add(self.row_override)

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

        self.btn_uninstall = Gtk.Button(label="Uninstall")
        self.btn_uninstall.add_css_class("destructive-action")
        self.btn_uninstall.connect("clicked", lambda *_: self._confirm())
        bottom.append(self.btn_uninstall)

        outer.append(bottom)
        return outer

    def detect_mode(self):
        """Detect current installation mode"""
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
                return

            # Not found
            self._detected_mode = "unknown"
            self.row_detected.set_subtitle("No active installation found")
            self.lbl_service.set_text("No service detected")

        except Exception as e:
            self._detected_mode = "unknown"
            self.row_detected.set_subtitle("Detection failed")
            self.lbl_service.set_text(str(e))

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
        self.btn_uninstall.set_sensitive(not busy)
        self.row_override.set_sensitive(not busy)
