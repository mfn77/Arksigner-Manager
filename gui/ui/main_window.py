import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Adw

from gui.core.logging import gui_log
from gui.core.privileged import build_pkexec_cmd, run_pkexec_stream, RunResult
from gui.ui.diagnostics_sidebar import DiagnosticsSidebar
from gui.ui.pages.actions_page import ActionsPage
from gui.ui.pages.install_setup_page import InstallSetupPage
from gui.ui.pages.upgrade_page import UpgradePage
from gui.ui.pages.progress_page import ProgressPage
from gui.ui.pages.post_install_page import PostInstallPage
from gui.ui.pages.uninstall_page import UninstallPage
from gui.ui.pages.purge_page import PurgePage
from gui.ui.pages.repair_page import RepairPage


class MainWindow(Adw.ApplicationWindow):
    PAGE_EMPTY = "empty"
    PAGE_INSTALL = "install"
    PAGE_UPGRADE = "upgrade"
    PAGE_PROGRESS = "progress"
    PAGE_POST = "post"
    PAGE_UNINSTALL = "uninstall"
    PAGE_PURGE = "purge"
    PAGE_REPAIR = "repair"
    PAGE_CONFIRM_PREFIX = "confirm-"

    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("ArkSigner Manager")
        self.set_default_size(1000, 650)
        # Minimum window size to prevent content clipping
        self.set_size_request(800, 780)  # Reduced width for narrower sidebar

        self._busy = False
        self._cancel_token = 0
        self._last_install_cfg = None
        self.last_output = "Ready.\n"

        gui_log("MainWindow init")

        # Toast overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Toolbar view
        tv = Adw.ToolbarView()
        self.toast_overlay.set_child(tv)

        # OverlaySplitView for diagnostics
        self.split = Adw.OverlaySplitView()
        self.split.set_sidebar_position(Gtk.PackType.START)
        self.split.set_show_sidebar(False)
        self.split.set_collapsed(True)
        self.split.set_enable_hide_gesture(True)
        self.split.set_enable_show_gesture(True)
        self.split.connect("notify::show-sidebar", self._on_sidebar_changed)

        # Diagnostics sidebar
        self.diag_sidebar = DiagnosticsSidebar(
            get_text_cb=lambda: self.last_output,
            save_cb=self.save_to_file,
            copy_cb=self.copy_diagnostics,
            on_close_cb=lambda: self.btn_diag.set_active(False),
        )
        self.split.set_sidebar(self.diag_sidebar)

        # Main content with Paned for responsive layout
        content_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_root.set_hexpand(True)
        content_root.set_vexpand(True)

        # Paned widget for resizable split
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(280)  # Default width (~GNOME Settings)
        self.paned.set_wide_handle(False)
        self.paned.set_shrink_start_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_resize_start_child(True)   # LEFT PANEL RESPONSIVE!
        self.paned.set_resize_end_child(True)
        
        # Connect to enforce max width
        self.paned.connect("notify::position", self._on_paned_position_changed)

        # LEFT PANEL (Actions + HeaderBar)
        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_panel.set_size_request(240, -1)  # Increased minimum
        left_panel.set_hexpand(False)  # Don't expand beyond natural size
        left_panel.set_halign(Gtk.Align.START)  # Stay on left
        # Dark sidebar like GNOME Settings
        left_panel.add_css_class("navigation-sidebar")

        # Left headerbar
        hb_left = Adw.HeaderBar()
        hb_left.add_css_class("flat")
        hb_left.set_show_end_title_buttons(False)
        hb_left.set_show_start_title_buttons(False)

        self.btn_diag = Gtk.ToggleButton()
        self.btn_diag.set_icon_name("sidebar-show-symbolic")
        self.btn_diag.add_css_class("flat")
        self.btn_diag.set_tooltip_text("Toggle Diagnostics")
        self.btn_diag.connect("toggled", self._on_diag_toggled)
        hb_left.pack_start(self.btn_diag)

        title_left = Gtk.Label(label="Menu")
        title_left.add_css_class("header-title")  # Custom class for bold + normal size
        hb_left.set_title_widget(title_left)
        
        # Hamburger menu on LEFT headerbar (GNOME Settings style)
        menu = Gio.Menu()
        menu.append("Status", "win.status")
        menu.append("About", "win.about")
        menu.append("Quit", "win.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        hb_left.pack_end(menu_btn)  # Right side of left headerbar

        left_panel.append(hb_left)

        # Actions page
        self.page_actions = ActionsPage(on_action=self.on_action_clicked)
        left_panel.append(self.page_actions.widget)

        self.paned.set_start_child(left_panel)

        # RIGHT PANEL (Content + HeaderBar)
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right_panel.set_hexpand(True)
        right_panel.set_size_request(500, -1)  # Minimum width for content

        # Right headerbar
        hb_right = Adw.HeaderBar()
        hb_right.add_css_class("flat")  # Same background as panel
        
        # Title (centered)
        self.title_right = Gtk.Label(label="")
        self.title_right.add_css_class("header-title")  # Custom class
        hb_right.set_title_widget(self.title_right)

        right_panel.append(hb_right)

        # Stack with pages
        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        right_panel.append(self.stack)

        self.page_install_setup = InstallSetupPage(on_confirm=self.on_install_confirm)
        self.page_upgrade = UpgradePage(on_confirm=self.on_upgrade_confirm)
        self.page_progress = ProgressPage(on_cancel=self.on_progress_cancel)
        self.page_post_install = PostInstallPage(
            on_done=self.on_post_install_done,
            on_firefox_add=self.on_post_install_firefox_add,
        )
        self.page_uninstall = UninstallPage(
            on_confirm=self.on_uninstall_confirm,
            on_cancel=lambda: self.stack.set_visible_child_name(self.PAGE_EMPTY)
        )
        self.page_purge = PurgePage(
            on_confirm=self.on_purge_confirm,
            on_cancel=lambda: self.stack.set_visible_child_name(self.PAGE_EMPTY)
        )
        self.page_repair = RepairPage(
            on_confirm=self.on_repair_confirm,
            on_cancel=lambda: self.stack.set_visible_child_name(self.PAGE_EMPTY)
        )

        self.stack.add_named(self._empty_widget(), self.PAGE_EMPTY)
        self.stack.add_named(self.page_install_setup.widget, self.PAGE_INSTALL)
        self.stack.add_named(self.page_upgrade.widget, self.PAGE_UPGRADE)
        self.stack.add_named(self.page_progress.widget, self.PAGE_PROGRESS)
        self.stack.add_named(self.page_post_install.widget, self.PAGE_POST)
        self.stack.add_named(self.page_uninstall.widget, self.PAGE_UNINSTALL)
        self.stack.add_named(self.page_purge.widget, self.PAGE_PURGE)
        self.stack.add_named(self.page_repair.widget, self.PAGE_REPAIR)
        self.stack.set_visible_child_name(self.PAGE_EMPTY)
        self.stack.connect("notify::visible-child-name", self._on_page_changed)

        self.paned.set_end_child(right_panel)

        content_root.append(self.paned)

        self.split.set_content(content_root)
        tv.set_content(self.split)

        # Add status action
        status_action = Gio.SimpleAction.new("status", None)
        status_action.connect("activate", lambda *_: self.run_status())
        self.add_action(status_action)

        # Add about action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", lambda *_: self.show_about())
        self.add_action(about_action)

        # Add quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: app.quit())
        self.add_action(quit_action)

        # CSS
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            /* COMPLETELY hide paned separator */
            paned > separator {
                background: transparent;
                background-image: none;
                background-color: transparent;
                border: none;
                box-shadow: none;
                min-width: 0;
                min-height: 0;
                margin: 0;
                padding: 0;
            }
            
            /* Also hide the handle */
            paned > separator handle {
                background: transparent;
                border: none;
                min-width: 0;
                min-height: 0;
            }
            
            /* Left sidebar - dark in dark mode, light gray in light mode */
            .navigation-sidebar {
                background-color: @headerbar_bg_color;
                min-width: 240px;
                max-width: 340px;
            }
            
            /* Light mode override - make sidebar light gray like GNOME Settings */
            @media (prefers-color-scheme: light) {
                .navigation-sidebar {
                    background-color: @sidebar_bg_color;
                    min-width: 240px;
                    max-width: 340px;
                }
            }
            
            /* Right panel - no special headerbar styling */
            /* Let it use default window background */
            
            /* Headerbar titles - bold but normal size */
            .header-title {
                font-weight: bold;
                font-size: 1em;  /* Normal body size */
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._refresh_diag()

    def _on_paned_position_changed(self, paned, param):
        """Enforce max width for left panel like GNOME Settings"""
        MAX_LEFT_WIDTH = 340  # GNOME Settings actual max
        MIN_LEFT_WIDTH = 240  # Increased for better visibility
        current = paned.get_position()
        
        if current > MAX_LEFT_WIDTH:
            paned.set_position(MAX_LEFT_WIDTH)
        elif current < MIN_LEFT_WIDTH:
            paned.set_position(MIN_LEFT_WIDTH)

    def _on_diag_toggled(self, button):
        is_active = button.get_active()
        self.split.set_show_sidebar(is_active)
        if is_active:
            self._refresh_diag()

    def _on_sidebar_changed(self, split, _param):
        is_shown = split.get_show_sidebar()
        if is_shown != self.btn_diag.get_active():
            self.btn_diag.set_active(is_shown)

    def _empty_widget(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        label = Gtk.Label(label="Select an action from the menu")
        label.add_css_class("title-2")
        label.add_css_class("dim-label")
        box.append(label)

        return box

    def _on_page_changed(self, stack, _param):
        page_name = stack.get_visible_child_name()
        title_map = {
            self.PAGE_EMPTY: "",
            self.PAGE_INSTALL: "Install",
            self.PAGE_UPGRADE: "Upgrade",
            self.PAGE_PROGRESS: "Progress",
            self.PAGE_POST: "Completed",
            self.PAGE_UNINSTALL: "Uninstall",
            self.PAGE_PURGE: "Purge",
            self.PAGE_REPAIR: "Repair",
        }
        if page_name and page_name.startswith(self.PAGE_CONFIRM_PREFIX):
            action = page_name[len(self.PAGE_CONFIRM_PREFIX):]
            self.title_right.set_text(f"Confirm {action.capitalize()}")
        else:
            self.title_right.set_text(title_map.get(page_name, ""))

    def toast(self, msg: str):
        t = Adw.Toast(title=msg)
        t.set_timeout(3)
        self.toast_overlay.add_toast(t)

    def set_busy(self, busy: bool):
        self._busy = bool(busy)
        self.page_actions.set_busy(self._busy)
        self.page_install_setup.set_busy(self._busy)
        self.page_upgrade.set_busy(self._busy)
        self.page_progress.set_busy(self._busy)
        self.page_post_install.set_busy(self._busy)
        self.page_uninstall.set_busy(self._busy)
        self.page_purge.set_busy(self._busy)
        self.page_repair.set_busy(self._busy)

        if self._busy:
            # Spinner removed - using progress page instead
            pass
        else:
            # Not busy
            pass

    def append_diag(self, line: str):
        self.last_output += line + "\n"
        if self.split.get_show_sidebar():
            self._refresh_diag()

    def _refresh_diag(self):
        self.diag_sidebar.refresh(self.last_output)

    def copy_diagnostics(self):
        clipboard = self.get_clipboard()
        clipboard.set(self.last_output)
        self.toast("Copied to clipboard")

    def save_to_file(self):
        self.page_actions.save_text_to_file(self.last_output)
        self.toast("Saved to file")

    def on_action_clicked(self, action: str):
        gui_log(f"Action clicked: {action}")

        if action == "install":
            self.stack.set_visible_child_name(self.PAGE_INSTALL)
        elif action == "upgrade":
            self._detect_mode_and_show_upgrade()
        elif action == "repair":
            self.page_repair.detect_mode()
            self.stack.set_visible_child_name(self.PAGE_REPAIR)
        elif action == "uninstall":
            self.page_uninstall.detect_mode()
            self.stack.set_visible_child_name(self.PAGE_UNINSTALL)
        elif action == "purge":
            self.page_purge.detect_mode()
            self.page_purge.reset()
            self.stack.set_visible_child_name(self.PAGE_PURGE)

    def run_status(self):
        if self._busy:
            self.toast("Busy")
            return

        self.btn_diag.set_active(True)
        self.append_diag("\n==== STATUS ====")
        cfg = self.page_install_setup.get_cfg()
        self.run_action("status", cfg=cfg, show_progress=False, auto_open_diag=True)

    def show_about(self):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="ArkSigner Manager",
            application_icon="tr.org.arksigner.Manager",
            developer_name="MFN",
            version="1.0.0",
            developers=["MFN"],
            copyright="© 2026 MFN",
            license_type=Gtk.License.GPL_3_0,
        )
        about.add_link("GitHub", "https://github.com/mfn77/Arksigner-Manager")
        about.present()

    def _confirm_widget(self, action: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        msg = {
            "repair": "Attempt to fix mounts/services and restart components.",
            "uninstall": "Remove services and mounts. Files may remain unless you purge.",
            "purge": "Remove everything including container rootfs (/var/lib/machines) or /opt files.",
        }.get(action, "Run selected action.")

        body = Gtk.Label(label=msg, xalign=0)
        body.add_css_class("dim-label")
        body.set_wrap(True)
        box.append(body)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda *_: self.stack.set_visible_child_name(self.PAGE_EMPTY))
        row.append(btn_cancel)

        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        row.append(spacer)

        btn_continue = Gtk.Button(label="Continue")
        if action in ("uninstall", "purge"):
            btn_continue.add_css_class("destructive-action")
        else:
            btn_continue.add_css_class("suggested-action")
        btn_continue.connect("clicked", lambda *_: self._continue_action(action))
        row.append(btn_continue)

        box.append(row)
        return box

    def _show_confirm_panel(self, action: str):
        name = self.PAGE_CONFIRM_PREFIX + action
        if self.stack.get_child_by_name(name) is None:
            self.stack.add_named(self._confirm_widget(action), name)
        self.stack.set_visible_child_name(name)

    def _continue_action(self, action: str):
        cfg = self.page_install_setup.get_cfg()
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset(f"{action.capitalize()}…")
        self.run_action(action, cfg=cfg, show_progress=True, auto_open_diag=False)

    def _detect_mode_and_show_upgrade(self):
        """Detect current installation mode by checking systemd units"""
        import subprocess

        try:
            p = subprocess.run(
                ["systemctl", "is-active", "arksigner-nspawn.service"],
                capture_output=True,
                text=True
            )
            if p.returncode == 0:
                mode = "container"
            else:
                p2 = subprocess.run(
                    ["systemctl", "is-active", "arksigner-native.service"],
                    capture_output=True,
                    text=True
                )
                mode = "native" if p2.returncode == 0 else "unknown"
        except Exception:
            mode = "unknown"

        self.page_upgrade.set_mode(mode)
        self.stack.set_visible_child_name(self.PAGE_UPGRADE)

    def on_upgrade_confirm(self, cfg):
        if cfg is None:
            self.stack.set_visible_child_name(self.PAGE_EMPTY)
            return

        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Upgrading…")
        self.run_action("upgrade", cfg=cfg, show_progress=True, auto_open_diag=False)

    def on_install_confirm(self, cfg: dict):
        self._last_install_cfg = cfg
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Installing…")
        self.run_action("install", cfg=cfg, show_progress=True, auto_open_diag=False, after_install=True)

    def on_progress_cancel(self):
        if not self._busy:
            self.toast("Nothing to cancel")
            return

        self._cancel_token += 1
        self.toast("Cancelling...")
        self.append_diag("Cancelled by user.")
        self.set_busy(False)
        self.stack.set_visible_child_name(self.PAGE_EMPTY)

    def on_post_install_done(self):
        self.stack.set_visible_child_name(self.PAGE_EMPTY)

    def on_post_install_firefox_add(self):
        if not self._last_install_cfg:
            self.toast("Missing install context")
            return
        cfg = dict(self._last_install_cfg)
        cfg["firefox_add"] = True
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Adding to Firefox…")
        self.run_action("status", cfg=cfg, show_progress=True, auto_open_diag=False)

    def on_uninstall_confirm(self, cfg):
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Uninstalling…")
        self.run_action("uninstall", cfg=cfg, show_progress=True, auto_open_diag=False)

    def on_purge_confirm(self, cfg):
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Purging…")
        self.run_action("purge", cfg=cfg, show_progress=True, auto_open_diag=False)

    def on_repair_confirm(self, cfg):
        self.stack.set_visible_child_name(self.PAGE_PROGRESS)
        self.page_progress.reset("Repairing…")
        self.run_action("repair", cfg=cfg, show_progress=True, auto_open_diag=False)

    def run_action(
        self,
        action: str,
        cfg: dict,
        show_progress: bool,
        auto_open_diag: bool,
        after_install: bool = False,
    ):
        if self._busy:
            self.toast("Busy")
            return

        token = self._cancel_token

        mode = cfg.get("mode", "container")
        machine = cfg.get("machine", "debian-arksigner")
        suite = cfg.get("suite", "bullseye")
        deb = cfg.get("deb", "")
        recreate = bool(cfg.get("recreate", False))
        native_rpath = bool(cfg.get("native_rpath", False))
        firefox_add = bool(cfg.get("firefox_add", False))
        
        # Repair-specific options
        force_terminate = bool(cfg.get("force_terminate", False))
        recreate_mounts = bool(cfg.get("recreate_mounts", False))
        clear_cache = bool(cfg.get("clear_cache", True))

        cmd = build_pkexec_cmd(
            action=action,
            mode=mode,
            machine=machine,
            suite=suite,
            deb=deb,
            firefox_add=firefox_add,
            recreate=recreate,
            native_rpath=native_rpath,
            force_terminate=force_terminate,
            recreate_mounts=recreate_mounts,
            clear_cache=clear_cache,
        )

        self.set_busy(True)

        self.append_diag(f"\n==== {action.upper()} (mode={mode}) ====")
        self.append_diag(f"Command: {' '.join(cmd)}")

        if auto_open_diag:
            self.btn_diag.set_active(True)

        def on_line(line: str):
            if token != self._cancel_token:
                return
            GLib.idle_add(self.append_diag, line)

        def on_progress(pct: int, msg: str):
            if token != self._cancel_token:
                return
            if show_progress:
                GLib.idle_add(self.page_progress.set_progress, pct, msg)

        def task():
            res = run_pkexec_stream(cmd, on_line=on_line, on_progress=on_progress)
            GLib.idle_add(self.finish_run, action, res, after_install, token)

        threading.Thread(target=task, daemon=True).start()

    def finish_run(self, action: str, res: RunResult, after_install: bool, token: int):
        if token != self._cancel_token:
            return

        self.set_busy(False)

        if res.rc == 0:
            self.toast("Done")
            if action == "install" and after_install:
                self.stack.set_visible_child_name(self.PAGE_POST)
            else:
                self.stack.set_visible_child_name(self.PAGE_EMPTY)
        else:
            self.toast(f"Failed with exit code: {res.rc}")
            self.append_diag(f"ERROR: exit code {res.rc}")
            self.stack.set_visible_child_name(self.PAGE_EMPTY)
