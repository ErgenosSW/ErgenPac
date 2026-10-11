from unittest import TestCase

from ergenpac.core import helper_command
from ergenpac.gaming import gaming_tool, missing_packages
from ergenpac.helper import command


class GamingTests(TestCase):
    def test_native_install_updates_system_and_includes_32_bit_support(self):
        self.assertEqual(command(["install-gaming", "mangohud"]), [
            "/usr/bin/pacman", "-Syu", "--needed", "--noconfirm",
            "mangohud", "lib32-mangohud",
        ])

    def test_partial_install_is_not_marked_complete(self):
        self.assertEqual(missing_packages(gaming_tool("gamemode"), {"gamemode"}),
                         ("lib32-gamemode",))
        self.assertEqual(missing_packages(gaming_tool("gamemode"),
                                         {"gamemode", "lib32-gamemode"}), ())

    def test_flatpak_targets_fixed_system_flathub_application(self):
        self.assertEqual(command(["install-gaming", "heroic"]), [
            "/usr/bin/flatpak", "install", "--system", "--noninteractive",
            "flathub", "com.heroicgameslauncher.hgl",
        ])

    def test_cannot_inject_package_or_flags_through_catalog(self):
        for identifier in ("--overwrite", "steam;id", "arbitrary-package", "../steam"):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    command(["install-gaming", identifier])
                with self.assertRaises(ValueError):
                    helper_command("install-gaming", identifier)
        with self.assertRaises(ValueError):
            command(["install-gaming", "steam", "--overwrite", "*"])

    def test_ui_request_uses_privileged_helper(self):
        self.assertEqual(helper_command("install-gaming", "gamescope"), [
            "pkexec", "/usr/lib/ergenpac/ergenpac-helper", "install-gaming", "gamescope",
        ])
