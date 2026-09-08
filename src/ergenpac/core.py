"""Pure package parsing and command construction for ErgenPac."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


PACKAGE_NAME = re.compile(r"^[A-Za-z0-9@._+:-]+$")
REBOOT_PACKAGES = ("linux", "systemd", "glibc", "nvidia", "mesa")
PROGRESS_PERCENT = re.compile(r"(?<!\d)(100|[1-9]?\d)%")
PROGRESS_SPEED = re.compile(r"(\d+(?:[.,]\d+)?\s*(?:B|KiB|MiB|GiB)/s)", re.IGNORECASE)
DOWNLOAD_TOTAL = re.compile(
    r"^Total Download Size\s*:\s*(\d+(?:[.,]\d+)?)\s*(B|KiB|MiB|GiB)",
    re.IGNORECASE,
)
TRANSFERRED_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(B|KiB|MiB|GiB)(?!/s)", re.IGNORECASE)


@dataclass(frozen=True)
class Package:
    repository: str
    name: str
    version: str
    description: str
    installed: bool = False
    backend: str = "pacman"
    identifier: str = ""


@dataclass(frozen=True)
class Update:
    name: str
    current_version: str
    new_version: str
    source: str = "System repositories"
    backend: str = "pacman"


@dataclass(frozen=True)
class DriverRecommendation:
    category: str
    hardware: str
    packages: tuple[str, ...]


DRIVER_PACKAGES = frozenset({
    "amd-ucode",
    "intel-ucode",
    "lib32-mesa",
    "lib32-nvidia-utils",
    "lib32-vulkan-intel",
    "lib32-vulkan-radeon",
    "linux-firmware",
    "linux-zen-headers",
    "mesa",
    "nvidia-open-dkms",
    "nvidia-settings",
    "nvidia-utils",
    "vulkan-intel",
    "vulkan-radeon",
})


def recommend_drivers(
    pci_output: str, cpuinfo: str, *, multilib: bool
) -> list[DriverRecommendation]:
    recommendations: list[DriverRecommendation] = []
    vendor_match = re.search(r"^vendor_id\s*:\s*(\S+)", cpuinfo, re.MULTILINE)
    vendor = vendor_match.group(1) if vendor_match else ""
    if vendor == "GenuineIntel":
        recommendations.append(
            DriverRecommendation("Processor", "Intel processor", ("intel-ucode",))
        )
    elif vendor == "AuthenticAMD":
        recommendations.append(
            DriverRecommendation("Processor", "AMD processor", ("amd-ucode",))
        )

    gpu_lines = [
        line.strip() for line in pci_output.splitlines()
        if re.search(r"\b(VGA compatible controller|3D controller|Display controller)\b", line)
    ]
    for line in gpu_lines:
        lowered = line.casefold()
        if "nvidia" in lowered:
            modern_nvidia = re.search(
                r"\bRTX\b|\bGTX\s*16\d\d\b|\b(?:TU|GA|AD|GB)\d{3}\b",
                line,
                re.IGNORECASE,
            )
            if modern_nvidia:
                packages = [
                    "linux-zen-headers", "nvidia-open-dkms", "nvidia-utils",
                    "nvidia-settings",
                ]
                if multilib:
                    packages.append("lib32-nvidia-utils")
                recommendations.append(
                    DriverRecommendation("NVIDIA graphics", line, tuple(packages))
                )
            else:
                recommendations.append(
                    DriverRecommendation(
                        "NVIDIA graphics — manual selection required", line, ()
                    )
                )
        elif (
            "amd" in lowered
            or "advanced micro devices" in lowered
            or re.search(r"\bATI\b", line, re.IGNORECASE)
        ):
            packages = ["mesa", "vulkan-radeon"]
            if multilib:
                packages.extend(("lib32-mesa", "lib32-vulkan-radeon"))
            recommendations.append(DriverRecommendation("Graphics", line, tuple(packages)))
        elif "intel" in lowered:
            packages = ["mesa", "vulkan-intel"]
            if multilib:
                packages.extend(("lib32-mesa", "lib32-vulkan-intel"))
            recommendations.append(DriverRecommendation("Graphics", line, tuple(packages)))
    return recommendations


def parse_search_output(output: str, installed: set[str] | None = None) -> list[Package]:
    known = installed or set()
    packages: list[Package] = []
    lines = output.splitlines()
    index = 0
    while index < len(lines):
        header = lines[index].strip()
        index += 1
        if "/" not in header:
            continue
        identity, _, remainder = header.partition(" ")
        repository, name = identity.split("/", 1)
        version = remainder.split()[0] if remainder else "unknown"
        description_parts: list[str] = []
        while index < len(lines) and lines[index][:1].isspace():
            description_parts.append(lines[index].strip())
            index += 1
        packages.append(
            Package(
                repository=repository,
                name=name,
                version=version,
                description=" ".join(description_parts) or "No description",
                installed=name in known,
            )
        )
    return packages


def parse_updates(output: str) -> list[Update]:
    updates: list[Update] = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] == "->":
            updates.append(Update(fields[0], fields[1], fields[3]))
    return updates


def parse_flatpak_updates(output: str) -> list[Update]:
    updates: list[Update] = []
    for line in output.splitlines():
        fields = [field.strip() for field in line.split("\t")]
        if len(fields) < 4 or not fields[0]:
            continue
        identifier, name, version, origin = fields[:4]
        updates.append(
            Update(
                name=name or identifier,
                current_version="Installed",
                new_version=version or "Update available",
                source=origin or "Flathub",
                backend="flatpak",
            )
        )
    return updates


def parse_flatpak_search(output: str, installed: set[str] | None = None) -> list[Package]:
    known = installed or set()
    packages: list[Package] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 5 or not fields[0].strip():
            continue
        identifier, name, description, version, remote = (field.strip() for field in fields[:5])
        packages.append(
            Package(
                repository=remote or "flathub",
                name=name or identifier,
                version=version or "unknown",
                description=description or "No description",
                installed=identifier in known,
                backend="flatpak",
                identifier=identifier,
            )
        )
    return packages


def parse_flatpak_installed(output: str) -> list[Package]:
    packages: list[Package] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 5 or not fields[0].strip():
            continue
        identifier, name, description, version, remote = (field.strip() for field in fields[:5])
        packages.append(
            Package(
                repository=remote or "flathub",
                name=name or identifier,
                version=version or "unknown",
                description=description or "Installed Flatpak application",
                installed=True,
                backend="flatpak",
                identifier=identifier,
            )
        )
    return packages


def parse_pacman_info(output: str, installed: set[str] | None = None) -> list[Package]:
    known = installed or set()
    packages: list[Package] = []
    entry: dict[str, str] = {}

    def append_entry() -> None:
        name = entry.get("Name", "")
        if not name:
            return
        packages.append(
            Package(
                repository=entry.get("Repository", "Arch Linux"),
                name=name,
                version=entry.get("Version", "unknown"),
                description=entry.get("Description", "No description"),
                installed=name in known,
            )
        )

    for line in [*output.splitlines(), ""]:
        if not line.strip():
            append_entry()
            entry = {}
            continue
        if line[:1].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        entry[key.strip()] = value.strip()
    return packages


def parse_progress(line: str) -> tuple[float | None, str | None]:
    percent_match = PROGRESS_PERCENT.search(line)
    speed_match = PROGRESS_SPEED.search(line)
    fraction = int(percent_match.group(1)) / 100 if percent_match else None
    speed = speed_match.group(1).replace(",", ".") if speed_match else None
    return fraction, speed


def _bytes(value: str, unit: str) -> int:
    multipliers = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3}
    return round(float(value.replace(",", ".")) * multipliers[unit.lower()])


def parse_total_download_size(line: str) -> int | None:
    match = DOWNLOAD_TOTAL.search(line.strip())
    return _bytes(*match.groups()) if match else None


def parse_transferred_size(line: str) -> int | None:
    match = TRANSFERRED_SIZE.search(line)
    return _bytes(*match.groups()) if match else None


def parse_transfer_identifier(line: str) -> str | None:
    match = TRANSFERRED_SIZE.search(line)
    identifier = line[: match.start()].strip() if match else ""
    return identifier or None


def sort_packages(packages: list[Package], query: str) -> list[Package]:
    needle = query.casefold()

    def rank(package: Package) -> tuple[int, str]:
        name = package.name.casefold()
        identifier = package.identifier.casefold()
        if name == needle or identifier == needle:
            priority = 0
        elif name.startswith(needle) or identifier.startswith(needle):
            priority = 1
        elif needle in name or needle in identifier:
            priority = 2
        else:
            priority = 3
        return priority, name

    return sorted(packages, key=rank)


def parse_transaction_preview(output: str) -> tuple[int, int]:
    count = 0
    total = 0
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or not fields[0].strip():
            continue
        try:
            size = int(fields[1])
        except ValueError:
            continue
        count += 1
        total += size
    return count, total


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def friendly_error(output: str, status: int) -> str:
    message = output.lower()
    if status < 0 or status in {126, 130} or "not authorized" in message or "dismissed" in message:
        return "The operation was cancelled. No changes were made."
    if "unable to lock database" in message or "could not lock database" in message:
        return "The package database is busy. Close other package managers and try again."
    if "no space left" in message or "not enough free disk space" in message:
        return "There is not enough free disk space to complete this operation."
    if any(text in message for text in ("could not resolve host", "failed retrieving file", "network is unreachable")):
        return "The repositories could not be reached. Check the internet connection and try again."
    if "target not found" in message or "no remote refs found" in message:
        return "The selected application is no longer available from its repository."
    if "invalid or corrupted package" in message or "signature" in message:
        return "Package verification failed. Refresh the repositories and try again."
    return "The operation could not be completed. No further automatic changes will be attempted."


def validate_package_name(name: str) -> str:
    if not PACKAGE_NAME.fullmatch(name):
        raise ValueError("invalid package name")
    return name


def helper_command(action: str, package: str | None = None) -> list[str]:
    base = ["pkexec", "/usr/lib/ergenpac/ergenpac-helper"]
    if action == "upgrade" and package is None:
        return [*base, "upgrade"]
    if action == "reboot" and package is None:
        return [*base, "reboot"]
    if action in {"install", "remove", "install-flatpak", "remove-flatpak"} and package is not None:
        return [*base, action, validate_package_name(package)]
    raise ValueError("invalid package operation")


def driver_helper_command(packages: Sequence[str]) -> list[str]:
    validated = tuple(dict.fromkeys(validate_package_name(name) for name in packages))
    if not validated or any(name not in DRIVER_PACKAGES for name in validated):
        raise ValueError("invalid driver package selection")
    return ["pkexec", "/usr/lib/ergenpac/ergenpac-helper", "install-drivers", *validated]


def reboot_recommended(updates: list[Update]) -> bool:
    return any(update.name.startswith(REBOOT_PACKAGES) for update in updates)
