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
