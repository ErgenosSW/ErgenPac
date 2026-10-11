from unittest import TestCase

from ergenpac.helper import command, driver_post_install_commands


class HelperTests(TestCase):
    def test_install_performs_full_upgrade(self) -> None:
        self.assertEqual(
            command(["install", "ergenctl"]),
            ["/usr/bin/pacman", "-Syu", "--needed", "--noconfirm", "ergenctl"],
        )

    def test_remove_uses_recursive_cleanup(self) -> None:
        self.assertEqual(
            command(["remove", "ergenctl"]),
            ["/usr/bin/pacman", "-Rns", "--noconfirm", "ergenctl"],
        )

    def test_arbitrary_arguments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            command(["install", "foo", "--overwrite", "*"])

    def test_flatpak_install_is_limited_to_flathub(self) -> None:
        self.assertEqual(
            command(["install-flatpak", "org.example.App"]),
            [
                "/usr/bin/flatpak",
                "install",
                "--system",
                "--noninteractive",
                "flathub",
                "org.example.App",
            ],
        )

    def test_driver_install_is_restricted_to_allowlisted_packages(self) -> None:
        self.assertEqual(
            command([
                "install-drivers",
                "nvidia-open-dkms",
                "nvidia-utils",
                "switcheroo-control",
            ]),
            [
                "/usr/bin/pacman", "-Syu", "--needed", "--noconfirm",
                "nvidia-open-dkms", "nvidia-utils", "switcheroo-control",
            ],
        )
        with self.assertRaises(ValueError):
            command(["install-drivers", "arbitrary-package"])

    def test_reboot_is_an_exact_allowlisted_operation(self) -> None:
        self.assertEqual(command(["reboot"]), ["/usr/bin/systemctl", "reboot"])

    def test_update_verification_only_runs_ergenctl_read_only_check(self) -> None:
        self.assertEqual(
            command(["verify-update"]),
            ["/usr/bin/ergenctl", "verify-update", "--json"],
        )

    def test_hybrid_profile_enables_switcheroo_control_after_installation(self) -> None:
        self.assertEqual(
            driver_post_install_commands(["mesa", "switcheroo-control"]),
            [[
                "/usr/bin/systemctl",
                "enable",
                "--now",
                "switcheroo-control.service",
            ]],
        )
        self.assertEqual(driver_post_install_commands(["mesa"]), [])
