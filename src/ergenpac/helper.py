#!/usr/bin/python3
"""Restricted privileged helper for ErgenPac."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys


PACKAGE_NAME = re.compile(r"^[A-Za-z0-9@._+:-]+$")


def command(arguments: list[str]) -> list[str]:
    if arguments == ["upgrade"]:
        return ["/usr/bin/pacman", "-Syu", "--noconfirm"]
    if len(arguments) == 2 and arguments[0] in {"install", "remove"}:
        action, package = arguments
        if not PACKAGE_NAME.fullmatch(package):
            raise ValueError("invalid package name")
        if action == "install":
            return ["/usr/bin/pacman", "-Syu", "--needed", "--noconfirm", package]
        return ["/usr/bin/pacman", "-Rns", "--noconfirm", package]
    if len(arguments) == 2 and arguments[0] in {"install-flatpak", "remove-flatpak"}:
        action, application = arguments
        if not PACKAGE_NAME.fullmatch(application):
            raise ValueError("invalid Flatpak application ID")
        if action == "install-flatpak":
            return [
                "/usr/bin/flatpak",
                "install",
                "--system",
                "--noninteractive",
                "flathub",
                application,
            ]
        return [
            "/usr/bin/flatpak",
            "uninstall",
            "--system",
            "--noninteractive",
            application,
        ]
    raise ValueError("invalid operation")


def main() -> int:
    try:
        requested = command(sys.argv[1:])
    except ValueError as error:
        print(f"ergenpac-helper: {error}", file=sys.stderr)
        return 2
    if sys.argv[1:] == ["upgrade"]:
        result = subprocess.run(requested, check=False)
        if result.returncode != 0:
            return result.returncode
        if shutil.which("flatpak"):
            return subprocess.run(
                ["/usr/bin/flatpak", "update", "--system", "--noninteractive"],
                check=False,
            ).returncode
        return 0
    os.execv(requested[0], requested)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
