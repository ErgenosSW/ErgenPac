"""Curated optional gaming tools and their fixed installation targets."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GamingTool:
    id: str
    name: str
    description: str
    packages: tuple[str, ...]
    hint: str
    backend: str = "pacman"


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
