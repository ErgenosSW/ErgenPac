from unittest import TestCase

from ergenpac.helper import command


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
            command(["install-drivers", "nvidia-open-dkms", "nvidia-utils"]),
            [
                "/usr/bin/pacman", "-Syu", "--needed", "--noconfirm",
                "nvidia-open-dkms", "nvidia-utils",
            ],
        )
        with self.assertRaises(ValueError):
            command(["install-drivers", "arbitrary-package"])

    def test_reboot_is_an_exact_allowlisted_operation(self) -> None:
        self.assertEqual(command(["reboot"]), ["/usr/bin/systemctl", "reboot"])
