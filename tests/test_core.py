from unittest import TestCase

from ergenpac.core import (
    Package,
    Update,
    driver_helper_command,
    helper_command,
    parse_flatpak_search,
    parse_flatpak_installed,
    parse_flatpak_updates,
    parse_transaction_preview,
    parse_pacman_info,
    parse_total_download_size,
    parse_transferred_size,
    parse_transfer_identifier,
    parse_progress,
    parse_search_output,
    parse_updates,
    friendly_error,
    format_size,
    reboot_recommended,
    recommend_drivers,
    validate_package_name,
    sort_packages,
)


class SearchParsingTests(TestCase):
    def test_packages_and_descriptions_are_parsed(self) -> None:
        output = "core/pacman 7.1.0-1\n    A package manager\nergenos/ergenctl 1.0.0-1 [installed]\n    Recovery utility\n"
        packages = parse_search_output(output, {"ergenctl"})
        self.assertEqual([package.name for package in packages], ["pacman", "ergenctl"])
        self.assertEqual(packages[0].description, "A package manager")
        self.assertTrue(packages[1].installed)


class UpdateParsingTests(TestCase):
    def test_updates_are_parsed(self) -> None:
        updates = parse_updates("ergenctl 0.1.2-1 -> 1.0.0-1\n")
        self.assertEqual(updates, [Update("ergenctl", "0.1.2-1", "1.0.0-1")])

    def test_kernel_update_recommends_reboot(self) -> None:
        self.assertTrue(reboot_recommended([Update("linux-zen", "1", "2")]))
        self.assertFalse(reboot_recommended([Update("ergenctl", "1", "2")]))

    def test_flatpak_updates_are_parsed(self) -> None:
        updates = parse_flatpak_updates("org.gimp.GIMP\tGIMP\t3.0\tflathub\n")
        self.assertEqual(updates[0].backend, "flatpak")
        self.assertEqual(updates[0].source, "flathub")


class FlatpakParsingTests(TestCase):
    def test_flathub_results_are_parsed(self) -> None:
        output = "net.lutris.Lutris\tLutris\tOpen Gaming Platform\t0.5.22\tflathub\n"
        packages = parse_flatpak_search(output, {"net.lutris.Lutris"})
        self.assertEqual(packages[0].identifier, "net.lutris.Lutris")
        self.assertEqual(packages[0].backend, "flatpak")
        self.assertTrue(packages[0].installed)

    def test_installed_flatpaks_are_parsed(self) -> None:
        output = "net.lutris.Lutris\tLutris\tOpen Gaming Platform\t0.5.22\tflathub\n"
        package = parse_flatpak_installed(output)[0]
        self.assertEqual(package.identifier, "net.lutris.Lutris")
        self.assertTrue(package.installed)


class InstalledPackageParsingTests(TestCase):
    def test_pacman_info_is_parsed(self) -> None:
        output = "Repository : extra\nName : lutris\nVersion : 1.0\nDescription : Games\n\n"
        package = parse_pacman_info(output, {"lutris"})[0]
        self.assertEqual(package.repository, "extra")
        self.assertTrue(package.installed)


class ProgressParsingTests(TestCase):
    def test_percentage_and_speed_are_parsed(self) -> None:
        self.assertEqual(parse_progress("package 54% 2.8 MiB/s"), (0.54, "2.8 MiB/s"))

    def test_download_sizes_are_converted_to_bytes(self) -> None:
        self.assertEqual(parse_total_download_size("Total Download Size : 2.5 MiB"), 2621440)
        self.assertEqual(parse_transferred_size("foo 768.0 KiB 2.8 MiB/s 75%"), 786432)
        self.assertEqual(parse_transfer_identifier("foo 768.0 KiB 2.8 MiB/s 75%"), "foo")
        self.assertIsNone(parse_transferred_size("checking package integrity"))

class CommandTests(TestCase):
    def test_install_always_uses_restricted_helper(self) -> None:
        self.assertEqual(
            helper_command("install", "ergenctl"),
            ["pkexec", "/usr/lib/ergenpac/ergenpac-helper", "install", "ergenctl"],
        )

    def test_invalid_package_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_package_name("package; reboot")

    def test_flatpak_install_uses_restricted_helper(self) -> None:
        self.assertEqual(
            helper_command("install-flatpak", "net.lutris.Lutris"),
            [
                "pkexec",
                "/usr/lib/ergenpac/ergenpac-helper",
                "install-flatpak",
                "net.lutris.Lutris",
            ],
        )

    def test_driver_install_accepts_only_known_packages(self) -> None:
        self.assertEqual(
            driver_helper_command(["intel-ucode", "vulkan-intel"]),
            [
                "pkexec", "/usr/lib/ergenpac/ergenpac-helper", "install-drivers",
                "intel-ucode", "vulkan-intel",
            ],
        )
        with self.assertRaises(ValueError):
            driver_helper_command(["definitely-not-a-driver"])


class DriverRecommendationTests(TestCase):
    def test_intel_cpu_and_graphics_are_detected(self) -> None:
        recommendations = recommend_drivers(
            "00:02.0 VGA compatible controller: Intel Corporation UHD Graphics 620\n",
            "vendor_id\t: GenuineIntel\n",
            multilib=True,
        )
        packages = {package for item in recommendations for package in item.packages}
        self.assertIn("intel-ucode", packages)
        self.assertIn("vulkan-intel", packages)
        self.assertIn("lib32-vulkan-intel", packages)

    def test_modern_nvidia_uses_official_open_dkms_driver(self) -> None:
        recommendations = recommend_drivers(
            "01:00.0 3D controller: NVIDIA Corporation GeForce RTX 4060 Mobile\n",
            "vendor_id\t: GenuineIntel\n",
            multilib=False,
        )
        graphics = [item for item in recommendations if "NVIDIA" in item.category][0]
        self.assertIn("nvidia-open-dkms", graphics.packages)

    def test_unknown_nvidia_generation_requires_manual_selection(self) -> None:
        recommendations = recommend_drivers(
            "01:00.0 VGA compatible controller: NVIDIA Corporation Device 1380\n",
            "vendor_id\t: GenuineIntel\n",
            multilib=False,
        )
        graphics = [item for item in recommendations if "NVIDIA" in item.category][0]
        self.assertEqual(graphics.packages, ())


class PresentationTests(TestCase):
    def test_exact_search_results_are_sorted_first(self) -> None:
        packages = [
            Package("extra", "firefox-developer-edition", "1", ""),
            Package("extra", "firefox", "1", ""),
        ]
        self.assertEqual(sort_packages(packages, "firefox")[0].name, "firefox")

    def test_transaction_preview_is_summarized(self) -> None:
        self.assertEqual(parse_transaction_preview("foo\t1024\nbar\t2048\n"), (2, 3072))
        self.assertEqual(format_size(3072), "3.0 KiB")

    def test_common_errors_are_friendly(self) -> None:
        self.assertIn("database is busy", friendly_error("unable to lock database", 1))
        self.assertIn("cancelled", friendly_error("", 130))
