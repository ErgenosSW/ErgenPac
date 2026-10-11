<p align="center">
  <img src="assets/ergenpac-logo.png?v=2" alt="ErgenPac logo" width="420">
</p>

<h1 align="center">ErgenPac</h1>

<p align="center">
  Graphical package manager and system updater for ErgenOS.
</p>

The first release focuses on complete system updates, package search, installation and removal. Installing software always includes a full database refresh and system upgrade, preventing unsupported partial upgrades.

ErgenPac separates configured pacman repositories and Flathub results, shows user-facing installed applications, reports live operation progress with download speed, and refreshes package state automatically without blanking the current results. Third-party repositories configured in pacman, including Chaotic-AUR, are searched automatically.

## Features

- Combined pacman and Flatpak update view
- Hardware-aware Driver Manager for processor microcode, individual GPUs and
  complete AMD/Intel + NVIDIA hybrid laptop profiles
- Live search with exact-match ranking and category shortcuts
- Installed application view without core system package noise
- Transaction summary before package installation or removal
- Inline installation progress beside the selected package
- Aggregate update and driver download progress with safe cancellation before package deployment
- A centered restart action after a completed system update
- Automatic post-update verification through ErgenCTL, covering snapshots, boot files, GRUB, Secure Boot, kernel modules and failed services
- Friendly errors for offline repositories, locked databases, invalid signatures and low disk space
- Restricted polkit helper for privileged operations

Driver Manager uses packages from configured repositories and always shows the
proposed package list before authentication. Modern NVIDIA hardware uses the
official `nvidia-open-dkms` stack. Unknown or legacy NVIDIA generations are
flagged for manual review instead of receiving a potentially incompatible
driver. On systems configured with ErgenOS Secure Boot, DKMS driver
installation refreshes the signed boot components automatically.
Hybrid laptop profiles install the Mesa/Vulkan stack for the integrated GPU,
the official NVIDIA open DKMS stack for the discrete GPU, required 32-bit
gaming libraries when multilib is enabled, and `switcheroo-control` for desktop
GPU offloading.

## Optional gaming tools

The Gaming page offers Steam, Lutris, Heroic, Faugus, GameMode, MangoHud,
GOverlay and Gamescope. Each tool has its own install action and usage hint;
nothing is selected or installed automatically. GameMode and MangoHud include
32-bit libraries, and incomplete installations remain installable.

Native tools use configured pacman repositories, perform a complete system
upgrade and then run ErgenCTL verification. Heroic and Faugus use the system
Flathub remote. The page checks installed packages and refreshes repository metadata through
checkupdates in a private temporary database, without changing the system package
database or requiring administrator access. Failed refreshes are shown explicitly
and fall back to cached availability;
unavailable native packages or a missing/disabled Flathub remote disable the
corresponding install action. Refresh after changing repository configuration.
A confirmation shows the exact targets before authentication.

Configure graphics through Driver Manager first. Installing these tools does
not enable them globally. Native MangoHud/Gamescope do not automatically configure
Flatpak runtimes. Manage removal through Software → Installed; shared libraries
are not automatically removed by the Gaming page. ErgenProton-WoW is not yet
included in this catalog.

Sources: [Arch packages](https://archlinux.org/packages/),
[Heroic on Flathub](https://flathub.org/apps/com.heroicgameslauncher.hgl),
[Faugus on Flathub](https://flathub.org/apps/io.github.Faugus.faugus-launcher).

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Build:

```bash
meson setup build
meson compile -C build
```

Create an Arch package from a tagged source release:

```bash
makepkg -s
```

## Security

Unprivileged package discovery is separated from system-changing operations. ErgenPac uses a restricted polkit helper that accepts only complete upgrades and validated package install or remove requests.
