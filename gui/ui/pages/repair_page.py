import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class RepairPage:
    """
    Repair confirmation page with service status and options.
    """

    def __init__(self, on_confirm, on_cancel):
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._detected_mode = None
        self._service_status = "unknown"
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
            description="Current installation mode and service status",
        )
        page.add(grp_detect)

        self.row_detected = Adw.ActionRow(
            title="Detected Mode",
            subtitle="Detecting...",
        )
        self.lbl_mode = Gtk.Label(label="")
        self.lbl_mode.add_css_class("dim-label")
        self.lbl_mode.add_css_class("caption")
        self.row_detected.add_suffix(self.lbl_mode)
        grp_detect.add(self.row_detected)

        self.row_status = Adw.ActionRow(
            title="Service Status",
            subtitle="",
        )
        self.badge_status = Gtk.Label(label="unknown")
        self.badge_status.add_css_class("caption")
        self.badge_status.add_css_class("pill")
        self.row_status.add_suffix(self.badge_status)
        grp_detect.add(self.row_status)

        # Common issues that will be fixed
        grp_fixes = Adw.PreferencesGroup(
            title="Common Issues to Fix",
            description="This repair will attempt to fix these problems",
        )
        page.add(grp_fixes)

        fixes = [
            ("Restart services", "Stops and restarts ArkSigner services"),
            ("Fix stale mounts", "Unmounts and remounts bind mounts"),
            ("Cleanup unix-export", "Removes stuck export directories"),
            ("Reset failed units", "Clears systemd failed state"),
            ("Restore bind mounts", "Re-establishes PKCS#11 module access"),
        ]

        for title, subtitle in fixes:
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.set_activatable(False)
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
            row.add_prefix(icon)
            grp_fixes.add(row)

        # Advanced options
        grp_advanced = Adw.PreferencesGroup(
            title="Advanced Options",
            description="Optional repair actions (use with caution)",
        )
        page.add(grp_advanced)

        self.row_force_terminate = Adw.ActionRow(
            title="Force container terminate",
            subtitle="Forcefully stop container (container mode only)",
        )
        self.sw_force_terminate = Gtk.Switch()
        self.sw_force_terminate.set_valign(Gtk.Align.CENTER)
        self.row_force_terminate.add_suffix(self.sw_force_terminate)
        self.row_force_terminate.set_activatable_widget(self.sw_force_terminate)
        grp_advanced.add(self.row_force_terminate)

        self.row_recreate_mounts = Adw.ActionRow(
            title="Recreate bind mounts",
            subtitle="Remove and recreate all bind mounts from scratch",
        )
        self.sw_recreate_mounts = Gtk.Switch()
        self.sw_recreate_mounts.set_valign(Gtk.Align.CENTER)
        self.row_recreate_mounts.add_suffix(self.sw_recreate_mounts)
        self.row_recreate_mounts.set_activatable_widget(self.sw_recreate_mounts)
        grp_advanced.add(self.row_recreate_mounts)

        self.row_clear_cache = Adw.ActionRow(
            title="Clear systemd cache",
            subtitle="Run daemon-reload and reset-failed",
        )
        self.sw_clear_cache = Gtk.Switch()
        self.sw_clear_cache.set_valign(Gtk.Align.CENTER)
        self.sw_clear_cache.set_active(True)  # Default on
        self.row_clear_cache.add_suffix(self.sw_clear_cache)
        self.row_clear_cache.set_activatable_widget(self.sw_clear_cache)
        grp_advanced.add(self.row_clear_cache)

        # Mode override
        self.row_override = Adw.ComboRow(title="Mode Override")
        self.row_override.set_subtitle("Change only if auto-detection is wrong")
        self.row_override.set_model(Gtk.StringList.new(["Auto (recommended)", "container", "native"]))
        self.row_override.set_selected(0)
        grp_advanced.add(self.row_override)

        # Info banner
        grp_info = Adw.PreferencesGroup(title="")
        page.add(grp_info)

        info_row = Adw.ActionRow(
            title="Repair is non-destructive",
            subtitle="Your data and configuration will not be deleted",
        )
        info_row.set_activatable(False)
        icon_info = Gtk.Image.new_from_icon_name("emblem-system-symbolic")
        icon_info.add_css_class("accent")
        info_row.add_prefix(icon_info)
        grp_info.add(info_row)

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

        self.btn_repair = Gtk.Button(label="Repair")
        self.btn_repair.add_css_class("suggested-action")
        self.btn_repair.connect("clicked", lambda *_: self._confirm())
        bottom.append(self.btn_repair)

        outer.append(bottom)
        return outer

    def detect_mode(self):
        """Detect current installation mode and service status"""
        try:
            # Check container mode
            p = subprocess.run(
                ["systemctl", "is-active", "arksigner-nspawn.service"],
                capture_output=True,
                text=True
            )
            container_status = p.stdout.strip()

            if container_status in ("active", "activating", "failed", "inactive"):
                self._detected_mode = "container"
                self._service_status = container_status
                self.row_detected.set_subtitle("Container Mode")
                self.lbl_mode.set_text("arksigner-nspawn.service")
                self._update_status_badge(container_status)
                # Enable/disable container-specific options
                self.row_force_terminate.set_sensitive(True)
                return

            # Check native mode
            p2 = subprocess.run(
                ["systemctl", "is-active", "arksigner-native.service"],
                capture_output=True,
                text=True
            )
            native_status = p2.stdout.strip()

            if native_status in ("active", "activating", "failed", "inactive"):
                self._detected_mode = "native"
                self._service_status = native_status
                self.row_detected.set_subtitle("Native Mode")
                self.lbl_mode.set_text("arksigner-native.service")
                self._update_status_badge(native_status)
                # Disable container-specific options
                self.row_force_terminate.set_sensitive(False)
                return

            # Not found
            self._detected_mode = "unknown"
            self._service_status = "not-found"
            self.row_detected.set_subtitle("No active installation found")
            self.lbl_mode.set_text("No service detected")
            self._update_status_badge("not-found")
            self.row_force_terminate.set_sensitive(False)

        except Exception as e:
            self._detected_mode = "unknown"
            self._service_status = "error"
            self.row_detected.set_subtitle("Detection failed")
            self.lbl_mode.set_text(str(e))
            self._update_status_badge("error")
            self.row_force_terminate.set_sensitive(False)

    def _update_status_badge(self, status: str):
        """Update status badge with color"""
        # Remove all status classes
        self.badge_status.remove_css_class("success")
        self.badge_status.remove_css_class("warning")
        self.badge_status.remove_css_class("error")
        
        if status == "active":
            self.badge_status.set_text("active")
            self.badge_status.add_css_class("success")
            self.row_status.set_subtitle("Service is running normally")
        elif status in ("activating", "reloading"):
            self.badge_status.set_text(status)
            self.badge_status.add_css_class("warning")
            self.row_status.set_subtitle("Service is starting")
        elif status == "failed":
            self.badge_status.set_text("failed")
            self.badge_status.add_css_class("error")
            self.row_status.set_subtitle("Service has failed - repair recommended")
        elif status == "inactive":
            self.badge_status.set_text("inactive")
            self.badge_status.add_css_class("warning")
            self.row_status.set_subtitle("Service is not running")
        elif status == "not-found":
            self.badge_status.set_text("not found")
            self.badge_status.add_css_class("error")
            self.row_status.set_subtitle("No installation detected")
        else:
            self.badge_status.set_text(status)
            self.row_status.set_subtitle("")

    def _confirm(self):
        # Get mode (either detected or overridden)
        override_idx = self.row_override.get_selected()
        if override_idx == 0:  # Auto
            mode = self._detected_mode or "container"
        elif override_idx == 1:  # container
            mode = "container"
        else:  # native
            mode = "native"

        cfg = {
            "mode": mode,
            "force_terminate": self.sw_force_terminate.get_active(),
            "recreate_mounts": self.sw_recreate_mounts.get_active(),
            "clear_cache": self.sw_clear_cache.get_active(),
        }
        self._on_confirm(cfg)

    def set_busy(self, busy: bool):
        self.btn_repair.set_sensitive(not busy)
        self.row_override.set_sensitive(not busy)
        self.sw_force_terminate.set_sensitive(not busy and self._detected_mode == "container")
        self.sw_recreate_mounts.set_sensitive(not busy)
        self.sw_clear_cache.set_sensitive(not busy)
