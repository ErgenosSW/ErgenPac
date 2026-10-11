# Changelog

## 1.0.1 — 2026-10-11

- Refresh Gaming availability with checkupdates in a private temporary database.
- Accept both successful exit codes (updates available or no updates).
- Preserve cached availability with an explicit warning when refresh fails.
- Queue Gaming refresh when navigation occurs during another operation.
- Require fakeroot, which checkupdates needs even on a fresh installation.
- Add six regression tests; all 44 tests passed. The maintainer confirmed the
  fix in the VM and accepted the rebuilt ErgenOS 1.2 image.

## 1.0.0 — 2026-10-11

- Add the optional Gaming catalog: Steam, Lutris, Heroic, Faugus, GameMode,
  MangoHud, GOverlay and Gamescope.
- Include 32-bit GameMode/MangoHud packages, installed-state detection,
  repository availability checks, confirmations and per-tool usage hints.
- Install Heroic/Faugus through system Flathub; native tools use Pacman.
- Restrict privileged Gaming operations to fixed catalog identifiers.
- Verify the system through ErgenCTL after native Gaming installations.
- All 38 tests passed, along with an isolated GTK smoke test.

## 0.2.4

Redesign the interface with ErgenOS colors, a persistent navigation panel,
custom cards and animated navigation.

## 0.2.3

Run ErgenCTL verify-update after system updates and present its health/restart
result. Existing snap-pac hooks remain responsible for snapshots.

## 0.2.2

Add combined AMD/Intel + NVIDIA hybrid profiles, RTX 5050 PCI-ID recognition,
switcheroo-control activation and Secure Boot refresh after driver installation.

## Roadmap

Gaming Check and guided setup are deferred to 1.3. Installing a tool does not
enable it globally or configure the corresponding Flatpak runtime. No automated
ErgenProton-WoW installation is included in this release.
