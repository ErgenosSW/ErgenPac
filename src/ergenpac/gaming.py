"""Curated gaming tools and the read-only ErgenCTL Gaming Check report."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class GamingTool:
    id: str
    name: str
    description: str
    packages: tuple[str, ...]
    hint: str
    backend: str = "pacman"


@dataclass(frozen=True)
class GamingCheckReport:
    state: str
    summary: str
    recommended_tools: frozenset[str]
    driver_attention: bool


GAMING_TOOLS = (
    GamingTool("steam", "Steam", "Steam library and Windows games through Proton.",
               ("steam",), "Enable Steam Play for supported games in Steam settings."),
    GamingTool("lutris", "Lutris", "Manage games and launchers from multiple sources.",
               ("lutris",), "Choose runners and install games inside Lutris."),
    GamingTool("heroic", "Heroic", "Epic Games, GOG and Amazon libraries.",
               ("com.heroicgameslauncher.hgl",), "Sign in to your stores inside Heroic.", "flatpak"),
    GamingTool("faugus", "Faugus", "Run Windows games and launchers using Proton.",
               ("io.github.Faugus.faugus-launcher",), "Add a game or launcher inside Faugus.", "flatpak"),
    GamingTool("gamemode", "GameMode", "On-demand gaming optimizations, including 32-bit support.",
               ("gamemode", "lib32-gamemode"), "Steam launch options: gamemoderun %command%"),
    GamingTool("mangohud", "MangoHud", "FPS, frame times and hardware statistics, including 32-bit support.",
               ("mangohud", "lib32-mangohud"), "Steam launch options: mangohud %command%"),
    GamingTool("goverlay", "GOverlay", "Configure the MangoHud overlay visually.",
               ("goverlay", "mangohud", "lib32-mangohud"), "Open GOverlay to customize your overlay."),
    GamingTool("gamescope", "Gamescope", "Optional compositor for game resolution and scaling.",
               ("gamescope",), "Steam launch options: gamescope -f -- %command% — enable per game."),
)


OPTIONAL_CHECK_TO_TOOL = {
    "gaming-gamemode": "gamemode",
    "gaming-mangohud": "mangohud",
    "gaming-gamescope": "gamescope",
}

DRIVER_CHECKS = {
    "gaming-vulkan",
    "gaming-libraries",
    "gaming-libraries-64-bit",
    "gaming-libraries-32-bit",
    "gaming-driver-packages",
    "hybrid-graphics",
}


def parse_gaming_check(output: str) -> GamingCheckReport:
    """Validate ErgenCTL JSON and reduce it to safe UI recommendations."""
    try:
        payload = json.loads(output)
        checks = payload["checks"]
        if (
            payload.get("schema_version") != 1
            or payload.get("application") != "ErgenCTL"
            or not isinstance(checks, list)
        ):
            raise ValueError("incompatible report")

        normalized: list[tuple[str, str]] = []
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("invalid check")
            identifier = check.get("id")
            status = check.get("status")
            if not isinstance(identifier, str) or status not in {
                "pass", "warning", "fail", "unknown", "skipped"
            }:
                raise ValueError("invalid check")
            normalized.append((identifier, status))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid ErgenCTL Gaming Check report") from error

    recommended = frozenset(
        OPTIONAL_CHECK_TO_TOOL[identifier]
        for identifier, status in normalized
        if identifier in OPTIONAL_CHECK_TO_TOOL and status != "pass"
    )
    driver_attention = any(
        identifier in DRIVER_CHECKS and status in {"warning", "fail"}
        for identifier, status in normalized
    )
    failures = sum(status == "fail" for _identifier, status in normalized)
    warnings = sum(status == "warning" for _identifier, status in normalized)
    if failures:
        state = "critical"
        summary = f"Gaming Check found {failures} failure(s) and {warnings} warning(s)."
    elif warnings or driver_attention:
        state = "attention"
        summary = f"Gaming Check found {warnings} item(s) needing attention."
    else:
        state = "ready"
        summary = "Gaming Check found no driver or runtime failures."
    if recommended:
        summary += f" {len(recommended)} optional tool suggestion(s) are highlighted below."
    return GamingCheckReport(state, summary, recommended, driver_attention)


def gaming_tool(identifier: str) -> GamingTool:
    for tool in GAMING_TOOLS:
        if tool.id == identifier:
            return tool
    raise ValueError("unknown gaming tool")


def missing_packages(tool: GamingTool, installed: set[str]) -> tuple[str, ...]:
    return tuple(package for package in tool.packages if package not in installed)


def gaming_install_command(identifier: str) -> list[str]:
    tool = gaming_tool(identifier)
    if tool.backend == "flatpak":
        return ["/usr/bin/flatpak", "install", "--system", "--noninteractive", "flathub", *tool.packages]
    return ["/usr/bin/pacman", "-Syu", "--needed", "--noconfirm", *tool.packages]
