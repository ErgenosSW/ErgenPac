"""GTK4 and libadwaita interface for ErgenPac."""

from __future__ import annotations

import sys
import os
import errno
import pty
import select
import signal
import subprocess
import threading
from pathlib import Path
from collections.abc import Callable, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .core import (
    DriverRecommendation,
    Package,
    Update,
    driver_helper_command,
    format_size,
    friendly_error,
    helper_command,
    parse_flatpak_installed,
    parse_flatpak_search,
    parse_flatpak_updates,
    parse_pacman_info,
    parse_total_download_size,
    parse_transferred_size,
    parse_transfer_identifier,
    parse_progress,
    parse_search_output,
    parse_transaction_preview,
    parse_updates,
    reboot_recommended,
    recommend_drivers,
    sort_packages,
)


APPLICATION_ID = "io.github.ergenossw.ErgenPac"
CommandCallback = Callable[[int, str, str], None]


class ErgenPacWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application) -> None:
        super().__init__(application=application)
        self.set_title("ErgenPac")
        self.set_default_size(1040, 760)
        self._updates: list[Update] = []
        self._flatpak_updates: list[Update] = []
        self._installed: set[str] = set()
        self._installed_flatpaks: set[str] = set()
        self._pending_packages: list[Package] = []
        self._refresh_updates_after_search = False
        self._busy = False
        self._search_timer = 0
        self._queued_search = ""
        self._active_process: subprocess.Popen[bytes] | None = None
        self._cancel_requested = False
        self._cancel_button: Gtk.Button | None = None
        self._operation_label = "Operation"
        self._operation_backend = "pacman"
        self._operation_action = ""
        self._progress_window: Gtk.Window | None = None
        self._progress_bar: Gtk.ProgressBar | None = None
        self._progress_detail: Gtk.Label | None = None
        self._progress_total_bytes = 0
        self._progress_completed_bytes = 0
        self._progress_current_bytes = 0
        self._progress_transfer_identifier: str | None = None
        self._inline_progress: Gtk.ProgressBar | None = None
        self._inline_button: Gtk.Button | None = None
        self._driver_recommendations: list[DriverRecommendation] = []
        self._driver_packages: list[str] = []

        self._install_styles()

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        brand_icon = Gtk.Image.new_from_icon_name(APPLICATION_ID)
        brand_icon.set_pixel_size(32)
        brand_icon.set_tooltip_text("ErgenPac")
        brand_icon.set_margin_start(6)
        brand_icon.set_margin_end(6)
        header.pack_start(brand_icon)
        toolbar.add_top_bar(header)
        self.set_content(toolbar)

        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        toolbar.set_content(self.stack)

        self.stack.add_titled_with_icon(
            self._build_updates_page(), "updates", "Updates", "software-update-available-symbolic"
        )
        self.stack.add_titled_with_icon(
            self._build_software_page(), "software", "Software", "system-software-install-symbolic"
        )
        self.stack.add_titled_with_icon(
            self._build_drivers_page(), "drivers", "Driver Manager", "preferences-system-symbolic"
        )
        GLib.idle_add(self.check_updates)

    def _install_styles(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
          window { background: @window_bg_color; }
          headerbar { background: @headerbar_bg_color; }
          .ergen-page { padding: 30px; }
          .ergen-hero { padding: 18px 22px; border-radius: 16px; background: alpha(@accent_bg_color, 0.12); }
          .ergen-card { border-radius: 14px; }
          .inline-progress { min-width: 120px; }
          .success-action { padding: 18px; border-radius: 14px; background: alpha(@success_color, 0.12); }
        """)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_updates_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.add_css_class("ergen-page")

        title = Gtk.Label(label="System updates", xalign=0)
        title.add_css_class("title-1")
        page.append(title)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.update_status = Gtk.Label(label="Checking for updates...", xalign=0)
        self.update_status.set_hexpand(True)
        controls.append(self.update_status)

        self.refresh_button = Gtk.Button(label="Check again")
        self.refresh_button.connect("clicked", lambda _button: self.check_updates())
        controls.append(self.refresh_button)

        self.upgrade_button = Gtk.Button(label="Install updates")
        self.upgrade_button.add_css_class("suggested-action")
        self.upgrade_button.set_sensitive(False)
        self.upgrade_button.connect("clicked", self._confirm_upgrade)
        controls.append(self.upgrade_button)
        page.append(controls)

        self.reboot_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.reboot_box.set_halign(Gtk.Align.CENTER)
        self.reboot_box.add_css_class("success-action")
        reboot_label = Gtk.Label(label="Updates installed successfully")
        reboot_label.add_css_class("heading")
        self.reboot_box.append(reboot_label)
        self.reboot_button = Gtk.Button(label="Restart system")
        self.reboot_button.add_css_class("suggested-action")
        self.reboot_button.set_halign(Gtk.Align.CENTER)
        self.reboot_button.connect("clicked", self._confirm_reboot)
        self.reboot_box.append(self.reboot_button)
        self.reboot_box.set_visible(False)
        page.append(self.reboot_box)

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_vexpand(True)
        self.update_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.update_list.add_css_class("boxed-list")
        scrolled.set_child(self.update_list)
        page.append(scrolled)
        return page

    def _build_software_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.add_css_class("ergen-page")

        title = Gtk.Label(label="Software", xalign=0)
        title.add_css_class("title-1")
        page.append(title)

        modes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        modes.set_halign(Gtk.Align.CENTER)
        self.explore_button = Gtk.ToggleButton(label="Explore")
        self.explore_button.set_active(True)
        self.installed_button = Gtk.ToggleButton(label="Installed")
        self.installed_button.set_group(self.explore_button)
        self.explore_button.connect("toggled", self._software_mode_changed)
        self.installed_button.connect("toggled", self._software_mode_changed)
        modes.append(self.explore_button)
        modes.append(self.installed_button)
        page.append(modes)

        self.software_stack = Gtk.Stack()
        self.software_stack.set_vexpand(True)

        explore = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.search = Gtk.SearchEntry(placeholder_text="Search software")
        self.search.connect("activate", self._search_packages)
        self.search.connect("search-changed", self._schedule_search)
        explore.append(self.search)

        self.search_status = Gtk.Label(
            label="Search configured system repositories and Flathub", xalign=0
        )
        self.search_status.add_css_class("dim-label")
        explore.append(self.search_status)

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_vexpand(True)
        self.package_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        scrolled.set_child(self.package_results)
        explore.append(scrolled)
        self._show_categories()
        self.software_stack.add_named(explore, "explore")

        installed = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        installed_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.installed_status = Gtk.Label(label="Installed applications", xalign=0)
        self.installed_status.set_hexpand(True)
        self.installed_status.add_css_class("dim-label")
        installed_controls.append(self.installed_status)
        self.installed_refresh_button = Gtk.Button(label="Refresh")
        self.installed_refresh_button.connect("clicked", lambda _button: self._load_installed_apps())
        installed_controls.append(self.installed_refresh_button)
        installed.append(installed_controls)
        installed_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        installed_scroll.set_vexpand(True)
        self.installed_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        installed_scroll.set_child(self.installed_results)
        installed.append(installed_scroll)
        self.software_stack.add_named(installed, "installed")
        page.append(self.software_stack)
        return page

    def _build_drivers_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for setter in (
            page.set_margin_top,
            page.set_margin_bottom,
            page.set_margin_start,
            page.set_margin_end,
        ):
            setter(24)
        page.add_css_class("ergen-page")

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.add_css_class("ergen-hero")
        title = Gtk.Label(label="Driver Manager", xalign=0)
        title.add_css_class("title-1")
        hero.append(title)
        description = Gtk.Label(
            label=(
                "Detect graphics hardware and processor microcode, then install "
                "recommended packages from configured repositories."
            ),
            xalign=0,
            wrap=True,
        )
        description.add_css_class("dim-label")
        hero.append(description)
        page.append(hero)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.driver_status = Gtk.Label(label="Hardware has not been scanned yet", xalign=0)
        self.driver_status.set_hexpand(True)
        controls.append(self.driver_status)
        self.driver_scan_button = Gtk.Button(label="Scan hardware")
        self.driver_scan_button.connect("clicked", lambda _button: self._scan_drivers())
        controls.append(self.driver_scan_button)
        self.driver_install_button = Gtk.Button(label="Install recommended")
        self.driver_install_button.add_css_class("suggested-action")
        self.driver_install_button.set_sensitive(False)
        self.driver_install_button.connect("clicked", self._confirm_driver_install)
        controls.append(self.driver_install_button)
        page.append(controls)

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_vexpand(True)
        self.driver_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.driver_list.add_css_class("boxed-list")
        scrolled.set_child(self.driver_list)
        page.append(scrolled)
        return page

    def _scan_drivers(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.driver_status.set_text("Detecting hardware...")
        self._run(["lspci", "-nn"], self._drivers_pci_loaded)

    def _drivers_pci_loaded(self, status: int, output: str, error: str) -> None:
        if status != 0:
            self._set_busy(False)
            self.driver_status.set_text("Hardware detection failed")
            self._show_result("Driver scan failed", friendly_error(error or output, status))
            return
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        pacman_conf = Path("/etc/pacman.conf").read_text(encoding="utf-8", errors="replace")
        multilib = any(
            line.strip() == "[multilib]" for line in pacman_conf.splitlines()
            if not line.lstrip().startswith("#")
        )
        self._driver_recommendations = recommend_drivers(output, cpuinfo, multilib=multilib)
        self._run(["pacman", "-Qq"], self._drivers_installed_loaded)

    def _drivers_installed_loaded(self, status: int, output: str, _error: str) -> None:
        installed = set(output.splitlines()) if status == 0 else set()
        self._clear_list(self.driver_list)
        missing: list[str] = []
        manual_selection = False
        for recommendation in self._driver_recommendations:
            packages = recommendation.packages
            missing.extend(package for package in packages if package not in installed)
            complete = bool(packages) and all(package in installed for package in packages)
            manual_selection = manual_selection or not packages
            row = Adw.ActionRow(title=GLib.markup_escape_text(recommendation.category))
            row.set_subtitle(
                GLib.markup_escape_text(
                    f"{recommendation.hardware}\n"
                    + (
                        f"Recommended: {', '.join(packages)}"
                        if packages
                        else "This GPU generation needs a driver selected according to the ArchWiki."
                    )
                )
            )
            state = Gtk.Label(
                label=(
                    "Installed"
                    if complete
                    else "Manual review"
                    if not packages
                    else "Action available"
                )
            )
            state.add_css_class("success" if complete else "accent")
            row.add_suffix(state)
            self.driver_list.append(row)
        self._driver_packages = list(dict.fromkeys(missing))
        if not self._driver_recommendations:
            self.driver_list.append(
                Adw.ActionRow(
                    title="No supported hardware profile detected",
                    subtitle="The kernel may already provide the required driver.",
                )
            )
        if self._driver_packages:
            message = f"{len(self._driver_packages)} recommended package(s) are missing"
            if manual_selection:
                message += "; one device needs manual review"
        elif manual_selection:
            message = "One detected device needs manual driver selection"
        else:
            message = "Recommended driver packages are installed"
        self.driver_status.set_text(message)
        self._set_busy(False)

    def _confirm_driver_install(self, _button: Gtk.Button) -> None:
        packages = tuple(self._driver_packages)
        if not packages:
            return
        self._confirm(
            "Install recommended drivers?",
            "ErgenPac detected these missing packages:\n\n"
            + "\n".join(f"• {package}" for package in packages)
            + "\n\nA complete system upgrade will be performed first.",
            "Install",
            lambda: self._run_driver_install(packages),
        )

    def _run_driver_install(self, packages: Sequence[str]) -> None:
        self._set_busy(True)
        self._operation_label = "Recommended drivers installed"
        self._operation_backend = "pacman"
        self._operation_action = "install-drivers"
        self._cancel_requested = False
        self._show_progress("Installing drivers")
        self._run_streaming(driver_helper_command(packages), self._operation_finished)

    def _show_categories(self) -> None:
        self._clear_box(self.package_results)
        heading = Gtk.Label(label="Browse categories", xalign=0)
        heading.add_css_class("title-2")
        self.package_results.append(heading)
        categories = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12)
        for label, query, icon_name in (
            ("Internet", "browser", "web-browser-symbolic"),
            ("Games", "game", "applications-games-symbolic"),
            ("Multimedia", "media", "applications-multimedia-symbolic"),
            ("Development", "development", "applications-development-symbolic"),
            ("Graphics", "graphics", "applications-graphics-symbolic"),
            ("Office", "office", "x-office-document-symbolic"),
        ):
            button = Gtk.Button()
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            content.set_margin_top(12)
            content.set_margin_bottom(12)
            content.set_margin_start(18)
            content.set_margin_end(18)
            content.append(Gtk.Image.new_from_icon_name(icon_name))
            content.append(Gtk.Label(label=label))
            button.set_child(content)
            button.connect("clicked", lambda _button, value=query: self._category_selected(value))
            categories.append(button)
        self.package_results.append(categories)

    def _category_selected(self, query: str) -> None:
        self.search.set_text(query)
        if self._search_timer:
            GLib.source_remove(self._search_timer)
            self._search_timer = 0
        self._begin_search()

    def _schedule_search(self, _entry: Gtk.SearchEntry) -> None:
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        self._search_timer = GLib.timeout_add(450, self._debounced_search)

    def _debounced_search(self) -> bool:
        self._search_timer = 0
        query = self.search.get_text().strip()
        if not query:
            self.search_status.set_text("Search configured system repositories and Flathub")
            self._show_categories()
        elif len(query) >= 2:
            self._begin_search()
        return False

    def _software_mode_changed(self, button: Gtk.ToggleButton) -> None:
        if not button.get_active():
            return
        mode = "installed" if button is self.installed_button else "explore"
        self.software_stack.set_visible_child_name(mode)
        if mode == "installed" and not self._busy and not self.installed_results.get_first_child():
            self._load_installed_apps()

    def check_updates(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.update_status.set_text("Checking for updates...")
        self._run(["checkupdates"], self._updates_checked)

    def _updates_checked(self, status: int, output: str, error: str) -> None:
        if status not in {0, 2}:
            self._set_busy(False)
            self.update_status.set_text("Could not check for updates")
            self._show_result("Update check failed", friendly_error(error or output, status))
            return
        self._updates = parse_updates(output) if status == 0 else []
        self._run(
            [
                "flatpak", "remote-ls", "--system", "--updates", "--app",
                "--columns=application,name,version,origin",
            ],
            self._flatpak_updates_checked,
        )

    def _flatpak_updates_checked(self, status: int, output: str, _error: str) -> None:
        self._flatpak_updates = parse_flatpak_updates(output) if status == 0 else []
        self._set_busy(False)
        updates = [*self._updates, *self._flatpak_updates]
        count = len(updates)
        self._clear_list(self.update_list)
        if count == 0:
            self.update_status.set_text("Your system is up to date")
        else:
            self.update_status.set_text(f"{count} update(s) available")
        self.upgrade_button.set_sensitive(count > 0)
        for update in updates:
            row = Adw.ActionRow(title=GLib.markup_escape_text(update.name))
            row.set_subtitle(
                GLib.markup_escape_text(
                    f"{update.source}  -  {update.current_version}  ->  {update.new_version}"
                )
            )
            self.update_list.append(row)
        if self._queued_search:
            GLib.idle_add(self._begin_search)

    def _search_packages(self, _entry: Gtk.SearchEntry) -> None:
        if self._search_timer:
            GLib.source_remove(self._search_timer)
            self._search_timer = 0
        self._begin_search()

    def _begin_search(self) -> None:
        query = self.search.get_text().strip()
        if len(query) < 2:
            self.search_status.set_text("Enter at least two characters")
            return
        if self._busy:
            self._queued_search = query
            return
        self._queued_search = ""
        self._set_busy(True)
        self.search_status.set_text("Searching...")
        self._run(
            ["pacman", "-Qq"],
            lambda status, output, error: self._installed_loaded(query, status, output, error),
        )

    def _installed_loaded(self, query: str, status: int, output: str, error: str) -> None:
        if status != 0:
            self._set_busy(False)
            self.search_status.set_text("Could not read installed packages")
            self._show_result("Package query failed", error)
            return
        self._installed = set(output.splitlines())
        self._run(
            ["flatpak", "list", "--app", "--columns=application"],
            lambda result, stdout, stderr: self._flatpaks_loaded(query, result, stdout, stderr),
        )

    def _flatpaks_loaded(self, query: str, status: int, output: str, _error: str) -> None:
        self._installed_flatpaks = set(output.splitlines()) if status == 0 else set()
        self._run(
            ["pacman", "-Ss", query],
            lambda result, stdout, stderr: self._pacman_search_finished(
                query, result, stdout, stderr
            ),
        )

    def _pacman_search_finished(
        self, query: str, status: int, output: str, _error: str
    ) -> None:
        if status != 0 and not output.strip():
            self._pending_packages = []
        else:
            self._pending_packages = parse_search_output(output, self._installed)
        self._run(
            [
                "flatpak",
                "search",
                "--columns=application,name,description,version,remotes",
                query,
            ],
            lambda result, stdout, stderr: self._flatpak_search_finished(
                query, result, stdout, stderr
            ),
        )

    def _flatpak_search_finished(
        self, requested_query: str, status: int, output: str, _error: str
    ) -> None:
        self._set_busy(False)
        current_query = self.search.get_text().strip()
        if current_query != requested_query:
            GLib.idle_add(self._begin_search)
            return
        packages = list(self._pending_packages)
        if status == 0:
            packages.extend(parse_flatpak_search(output, self._installed_flatpaks))
        self.search_status.set_text(f"{len(packages)} package(s) found")
        query = requested_query
        arch = sort_packages(
            [package for package in packages if package.backend == "pacman"], query
        )[:50]
        flatpaks = sort_packages(
            [package for package in packages if package.backend == "flatpak"], query
        )[:50]
        self._render_package_groups(
            self.package_results,
            [("System repositories", arch), ("Flathub", flatpaks)],
        )
        if self._refresh_updates_after_search:
            self._refresh_updates_after_search = False
            GLib.idle_add(self.check_updates)

    def _package_row(self, package: Package) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=GLib.markup_escape_text(package.name),
            subtitle=GLib.markup_escape_text(
                f"{'Flatpak' if package.backend == 'flatpak' else package.repository}"
                f"  -  {package.version}\n{package.description}"
            ),
        )
        icon_name = package.identifier if package.backend == "flatpak" else package.name
        icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
        if not icon_theme.has_icon(icon_name):
            icon_name = "application-x-executable-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        row.add_prefix(icon)
        button = Gtk.Button(label="Remove" if package.installed else "Install")
        if not package.installed:
            button.add_css_class("suggested-action")
        button.set_valign(Gtk.Align.CENTER)
        progress = Gtk.ProgressBar(show_text=True, text="Preparing...")
        progress.add_css_class("inline-progress")
        progress.set_valign(Gtk.Align.CENTER)
        progress.set_visible(False)
        button.connect(
            "clicked",
            lambda _button: self._prepare_package_operation(package, progress, button),
        )
        row.add_suffix(progress)
        row.add_suffix(button)
        return row

    def _render_package_groups(
        self, container: Gtk.Box, groups: list[tuple[str, list[Package]]]
    ) -> None:
        replacement = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for heading, packages in groups:
            if not packages:
                continue
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            label = Gtk.Label(label=heading, xalign=0)
            label.add_css_class("heading")
            section.append(label)
            package_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            package_list.add_css_class("boxed-list")
            for package in packages:
                package_list.append(self._package_row(package))
            section.append(package_list)
            replacement.append(section)
        if not replacement.get_first_child():
            empty = Gtk.Label(label="No applications found")
            empty.add_css_class("dim-label")
            replacement.append(empty)
        self._clear_box(container)
        while child := replacement.get_first_child():
            replacement.remove(child)
            container.append(child)

    def _load_installed_apps(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.installed_status.set_text("Loading installed applications...")
        desktop_files = sorted(Path("/usr/share/applications").glob("*.desktop"))
        if desktop_files:
            self._run(
                ["pacman", "-Qqo", *[str(path) for path in desktop_files]],
                self._installed_desktop_owners_loaded,
            )
        else:
            self._installed_desktop_owners_loaded(0, "", "")

    def _installed_desktop_owners_loaded(self, status: int, output: str, _error: str) -> None:
        names = sorted(set(output.splitlines()))
        self._installed = set(names)
        if names:
            self._run(
                ["pacman", "-Qi", *names],
                self._installed_pacman_info_loaded,
            )
        else:
            self._installed_pacman_info_loaded(0, "", "")

    def _installed_pacman_info_loaded(self, _status: int, output: str, _error: str) -> None:
        self._pending_packages = parse_pacman_info(output, self._installed)
        self._run(
            [
                "flatpak", "list", "--app",
                "--columns=application,name,description,version,origin",
            ],
            self._installed_flatpaks_loaded,
        )

    def _installed_flatpaks_loaded(self, status: int, output: str, _error: str) -> None:
        flatpaks = parse_flatpak_installed(output) if status == 0 else []
        arch = sorted(self._pending_packages, key=lambda package: package.name.casefold())
        flatpaks.sort(key=lambda package: package.name.casefold())
        self._render_package_groups(
            self.installed_results,
            [("System applications", arch), ("Flathub applications", flatpaks)],
        )
        self.installed_status.set_text(f"{len(arch) + len(flatpaks)} installed application(s)")
        self._set_busy(False)

    def _confirm_upgrade(self, _button: Gtk.Button) -> None:
        self._confirm(
            "Install all updates?",
            "ErgenPac will perform a complete system upgrade.",
            "Install",
            lambda: self._run_privileged("upgrade"),
        )

    def _confirm_reboot(self, _button: Gtk.Button) -> None:
        self._confirm(
            "Restart the system?",
            "Save your work before continuing. The computer will restart immediately.",
            "Restart",
            self._reboot_system,
        )

    def _reboot_system(self) -> None:
        self._set_busy(True)
        self.reboot_button.set_label("Restarting...")
        self._run_streaming(helper_command("reboot"), self._reboot_finished)

    def _reboot_finished(self, status: int, output: str, error: str) -> None:
        if status != 0:
            self._set_busy(False)
            self.reboot_button.set_label("Restart system")
            self._show_result("Restart failed", friendly_error(error or output, status))

    def _prepare_package_operation(
        self, package: Package, progress: Gtk.ProgressBar, button: Gtk.Button
    ) -> None:
        if package.backend == "flatpak":
            action = "remove-flatpak" if package.installed else "install-flatpak"
            target = package.identifier
            self._confirm_package(
                action,
                target,
                package,
                f"Source: {package.repository}\nDependencies will be resolved automatically.",
                progress,
                button,
            )
            return
        action = "remove" if package.installed else "install"
        operation = "-Rp" if package.installed else "-Sp"
        self._set_busy(True)
        self.search_status.set_text("Preparing transaction...")
        self._run(
            ["pacman", operation, "--print-format", "%n\t%s", package.name],
            lambda status, output, error: self._preview_loaded(
                action, package.name, package, progress, button, status, output, error
            ),
        )

    def _preview_loaded(
        self,
        action: str,
        target: str,
        package: Package,
        progress: Gtk.ProgressBar,
        button: Gtk.Button,
        status: int,
        output: str,
        _error: str,
    ) -> None:
        self._set_busy(False)
        count, size = parse_transaction_preview(output) if status == 0 else (0, 0)
        summary = f"Source: {package.repository}"
        if count:
            label = "Download" if action == "install" else "Affected size"
            summary += f"\nPackages affected: {count}\n{label}: {format_size(size)}"
        else:
            summary += "\nDependencies will be resolved automatically."
        self._confirm_package(action, target, package, summary, progress, button)

    def _confirm_package(
        self,
        action: str,
        target: str,
        package: Package,
        summary: str,
        progress: Gtk.ProgressBar,
        button: Gtk.Button,
    ) -> None:
        verb = "Install" if action.startswith("install") else "Remove"
        detail = (
            "Installing software also updates the complete system."
            if action.startswith("install")
            else "Unused dependencies installed with this package will also be removed."
        )
        self._confirm(
            f"{verb} {package.name}?",
            f"{summary}\n\n{detail}",
            verb,
            lambda: self._run_privileged(
                action,
                target,
                f"{package.name} {'installed' if verb == 'Install' else 'removed'}",
                progress,
                button,
            ),
        )

    def _confirm(
        self, heading: str, body: str, action_label: str, callback: Callable[[], None]
    ) -> None:
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("continue", action_label)
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _dialog, response: callback() if response == "continue" else None)
        dialog.present()

    def _run_privileged(
        self,
        action: str,
        package: str | None = None,
        result_label: str = "Operation completed",
        inline_progress: Gtk.ProgressBar | None = None,
        inline_button: Gtk.Button | None = None,
    ) -> None:
        self._set_busy(True)
        self._operation_label = result_label
        self._operation_backend = "flatpak" if "flatpak" in action else "pacman"
        self._operation_action = action
        self._cancel_requested = False
        self._inline_progress = inline_progress
        self._inline_button = inline_button
        if inline_progress is not None:
            inline_progress.set_fraction(0.0)
            inline_progress.set_text("Preparing...")
            inline_progress.set_visible(True)
        if inline_button is not None:
            inline_button.set_visible(False)
        self.update_status.set_text("Applying changes...")
        if inline_progress is None:
            self._show_progress("Installing updates" if action == "upgrade" else "Applying changes")
        self._run_streaming(helper_command(action, package), self._operation_finished)

    def _operation_finished(self, status: int, output: str, error: str) -> None:
        self._hide_progress()
        self._set_busy(False)
        if status == 0:
            result = "The software state was refreshed successfully."
            if self._operation_action == "upgrade":
                self.reboot_box.set_visible(True)
                if reboot_recommended(self._updates):
                    result += "\n\nA restart is recommended to finish applying system updates."
            self._show_result(self._operation_label, result)
            if self._operation_action == "install-drivers":
                GLib.idle_add(self._scan_drivers)
                return
            self._clear_box(self.installed_results)
            if self.software_stack.get_visible_child_name() == "installed":
                self._load_installed_apps()
            elif len(self.search.get_text().strip()) >= 2:
                self._refresh_updates_after_search = True
                self._search_packages(self.search)
            else:
                self.check_updates()
        else:
            effective_status = 130 if self._cancel_requested else status
            self._show_result("Operation failed", friendly_error(error or output, effective_status))

    def _show_progress(self, heading: str) -> None:
        window = Gtk.Window(title=heading, transient_for=self, modal=True, resizable=False)
        window.set_deletable(False)
        window.set_default_size(420, 150)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(28)
        box.set_margin_bottom(28)
        box.set_margin_start(28)
        box.set_margin_end(28)
        label = Gtk.Label(label=heading)
        label.add_css_class("title-2")
        box.append(label)
        progress = Gtk.ProgressBar(show_text=True, text="Preparing...")
        box.append(progress)
        detail = Gtk.Label(label="Speed: --", xalign=0)
        detail.add_css_class("dim-label")
        box.append(detail)
        cancel = Gtk.Button(label="Cancel")
        cancel.set_halign(Gtk.Align.END)
        cancel.connect("clicked", self._cancel_operation)
        box.append(cancel)
        window.set_child(box)
        window.present()
        self._progress_window = window
        self._progress_bar = progress
        self._progress_detail = detail
        self._cancel_button = cancel
        self._progress_total_bytes = 0
        self._progress_completed_bytes = 0
        self._progress_current_bytes = 0
        self._progress_transfer_identifier = None

    def _progress_line(self, line: str) -> None:
        progress_bars = [
            bar for bar in (self._progress_bar, self._inline_progress) if bar is not None
        ]
        if not progress_bars:
            return

        def update_progress(*, fraction: float | None = None, text: str) -> None:
            for bar in progress_bars:
                if fraction is None:
                    bar.pulse()
                else:
                    bar.set_fraction(fraction)
                bar.set_text(text)

        clean = line.strip()
        if not clean:
            return
        if "Processing package changes" in clean and self._cancel_button is not None:
            self._cancel_button.set_sensitive(False)
        total_bytes = parse_total_download_size(clean)
        if total_bytes:
            self._progress_total_bytes = total_bytes
            self._progress_completed_bytes = 0
            self._progress_current_bytes = 0
            self._progress_transfer_identifier = None
            update_progress(fraction=0.0, text="0%")
            return
        fraction, speed = parse_progress(clean)
        transferred = parse_transferred_size(clean)
        identifier = parse_transfer_identifier(clean)
        if fraction is not None and speed and transferred is not None:
            if (
                self._progress_transfer_identifier is not None
                and identifier != self._progress_transfer_identifier
            ):
                self._progress_completed_bytes += self._progress_current_bytes
            self._progress_current_bytes = transferred
            self._progress_transfer_identifier = identifier
            if self._progress_total_bytes:
                overall = min(
                    1.0,
                    (self._progress_completed_bytes + transferred) / self._progress_total_bytes,
                )
                update_progress(fraction=overall, text=f"{round(overall * 100)}%")
            else:
                update_progress(text="Downloading...")
        elif fraction is not None and self._operation_backend == "flatpak":
            update_progress(fraction=fraction, text=f"{round(fraction * 100)}%")
        if self._progress_detail is not None and speed:
            self._progress_detail.set_text(f"Speed: {speed}")

    def _hide_progress(self) -> None:
        if self._progress_window is not None:
            self._progress_window.close()
        self._progress_window = None
        self._progress_bar = None
        self._progress_detail = None
        self._cancel_button = None
        self._active_process = None
        if self._inline_progress is not None:
            self._inline_progress.set_visible(False)
        if self._inline_button is not None:
            self._inline_button.set_visible(True)
        self._inline_progress = None
        self._inline_button = None

    def _cancel_operation(self, _button: Gtk.Button) -> None:
        process = self._active_process
        if process is None or process.poll() is not None:
            return
        self._cancel_requested = True
        if self._cancel_button is not None:
            self._cancel_button.set_sensitive(False)
            self._cancel_button.set_label("Cancelling...")
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.refresh_button.set_sensitive(not busy)
        self.search.set_sensitive(not busy)
        self.explore_button.set_sensitive(not busy)
        self.installed_button.set_sensitive(not busy)
        self.installed_refresh_button.set_sensitive(not busy)
        self.upgrade_button.set_sensitive(not busy and bool(self._updates))
        self.driver_scan_button.set_sensitive(not busy)
        self.driver_install_button.set_sensitive(not busy and bool(self._driver_packages))
        self.reboot_button.set_sensitive(not busy)

    def _run(self, arguments: Sequence[str], callback: CommandCallback) -> None:
        launcher = Gio.SubprocessLauncher(
            flags=Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        )
        launcher.setenv("LC_ALL", "C", True)
        try:
            process = launcher.spawnv(list(arguments))
        except GLib.Error as error:
            callback(127, "", str(error))
            return

        def completed(subprocess: Gio.Subprocess, result: Gio.AsyncResult) -> None:
            try:
                _ok, stdout, stderr = subprocess.communicate_utf8_finish(result)
                callback(subprocess.get_exit_status(), stdout or "", stderr or "")
            except GLib.Error as error:
                callback(1, "", str(error))

        process.communicate_utf8_async(None, None, completed)

    def _run_streaming(self, arguments: Sequence[str], callback: CommandCallback) -> None:
        def worker() -> None:
            output: list[str] = []
            master = -1
            slave = -1
            try:
                environment = os.environ.copy()
                environment["LC_ALL"] = "C"
                environment["COLUMNS"] = "80"
                master, slave = pty.openpty()
                process = subprocess.Popen(
                    list(arguments),
                    stdin=subprocess.DEVNULL,
                    stdout=slave,
                    stderr=slave,
                    env=environment,
                    close_fds=True,
                    start_new_session=True,
                )
                self._active_process = process
                os.close(slave)
                slave = -1
                pending = ""
                while process.poll() is None or select.select([master], [], [], 0)[0]:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if not ready:
                        continue
                    try:
                        chunk = os.read(master, 4096).decode("utf-8", errors="replace")
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output.append(chunk)
                    pending += chunk.replace("\r", "\n")
                    lines = pending.split("\n")
                    pending = lines.pop()
                    for line in lines:
                        GLib.idle_add(self._progress_line, line)
                if pending:
                    GLib.idle_add(self._progress_line, pending)
                status = process.wait()
                combined = "".join(output)
                GLib.idle_add(callback, status, combined, combined if status else "")
            except OSError as error:
                GLib.idle_add(callback, 127, "", str(error))
            finally:
                if slave >= 0:
                    os.close(slave)
                if master >= 0:
                    os.close(master)

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, heading: str, details: str) -> None:
        body = details.strip()[-4000:] or "No additional details."
        dialog = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dialog.add_response("close", "Close")
        dialog.present()

    @staticmethod
    def _clear_list(list_box: Gtk.ListBox) -> None:
        while child := list_box.get_first_child():
            list_box.remove(child)

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        while child := box.get_first_child():
            box.remove(child)


class ErgenPacApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APPLICATION_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = ErgenPacWindow(self)
        window.present()


def main() -> int:
    Adw.init()
    return ErgenPacApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
    driver_helper_command,
