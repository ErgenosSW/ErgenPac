from unittest import TestCase

from ergenpac.core import (
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
    parse_progress,
    parse_search_output,
    parse_total_download_size,
    parse_transaction_preview,
    parse_transfer_identifier,
    parse_transferred_size,
    parse_update_verification,
    parse_updates,
    reboot_recommended,
    recommend_drivers,
    sort_packages,
    update_verification_message,
    validate_package_name,
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

    def test_ergenctl_update_verification_is_parsed(self) -> None:
        report = parse_update_verification(
            '{"schema_version":1,"application":"ErgenCTL","update_verification":'
            '{"state":"attention","success":true,"reboot_required":false,"checks":['
            '{"status":"warning","summary":"one failed service"}]}}'
        )

        self.assertEqual(report.state, "attention")
        self.assertEqual(report.problems, ("one failed service",))
        self.assertIn("one failed service", update_verification_message(report))

    def test_incompatible_update_verification_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_update_verification('{"schema_version":2,"application":"ErgenCTL"}')


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

    def test_update_verification_uses_restricted_helper(self) -> None:
        self.assertEqual(
            helper_command("verify-update"),
            ["pkexec", "/usr/lib/ergenpac/ergenpac-helper", "verify-update"],
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

    def test_amd_nvidia_laptop_uses_one_complete_hybrid_profile(self) -> None:
        recommendations = recommend_drivers(
            "04:00.0 VGA compatible controller [0300]: Advanced Micro Devices, Inc. "
            "Radeon 860M [1002:150e]\n"
            "01:00.0 3D controller [0302]: NVIDIA Corporation GeForce RTX 5050 "
            "Laptop GPU [10de:2d98]\n",
            "vendor_id\t: AuthenticAMD\n",
            multilib=True,
        )

        graphics = [item for item in recommendations if "graphics" in item.category.casefold()]
        self.assertEqual(len(graphics), 1)
        self.assertEqual(graphics[0].category, "Hybrid graphics — AMD + NVIDIA")
        self.assertIn("Radeon 860M", graphics[0].hardware)
        self.assertIn("RTX 5050", graphics[0].hardware)
        self.assertEqual(len(graphics[0].packages), len(set(graphics[0].packages)))
        self.assertTrue(
            {
                "linux-firmware",
                "mesa",
                "vulkan-radeon",
                "lib32-mesa",
                "lib32-vulkan-radeon",
                "linux-zen-headers",
                "nvidia-open-dkms",
                "nvidia-utils",
                "nvidia-settings",
                "lib32-nvidia-utils",
                "switcheroo-control",
            }.issubset(graphics[0].packages)
        )

    def test_unresolved_rtx_5050_pci_ids_are_recognized_as_blackwell(self) -> None:
        for device_id in ("2d98", "2dd8"):
            with self.subTest(device_id=device_id):
                recommendations = recommend_drivers(
                    f"01:00.0 3D controller [0302]: NVIDIA Corporation Device {device_id} "
                    f"[10de:{device_id}]\n",
                    "vendor_id\t: AuthenticAMD\n",
                    multilib=False,
                )
                graphics = next(
                    item for item in recommendations if "NVIDIA" in item.category
                )
                self.assertIn("nvidia-open-dkms", graphics.packages)

    def test_unknown_nvidia_device_does_not_create_unsafe_hybrid_profile(self) -> None:
        recommendations = recommend_drivers(
            "04:00.0 VGA compatible controller: Advanced Micro Devices, Inc. Radeon Graphics\n"
            "01:00.0 3D controller: NVIDIA Corporation Device 1380\n",
            "vendor_id\t: AuthenticAMD\n",
            multilib=True,
        )

        self.assertFalse(any("Hybrid" in item.category for item in recommendations))
        manual = next(item for item in recommendations if "manual" in item.category)
        self.assertEqual(manual.packages, ())
        amd = next(item for item in recommendations if item.category == "Graphics")
        self.assertNotIn("switcheroo-control", amd.packages)

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
