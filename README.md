<p align="center">
  <img src="assets/ergenpac-logo.png" alt="ErgenPac logo" width="420">
</p>

<h1 align="center">ErgenPac</h1>

<p align="center">
  Graphical package manager and system updater for ErgenOS.
</p>

The first release focuses on complete system updates, package search, installation and removal. Installing software always includes a full database refresh and system upgrade, preventing unsupported partial upgrades.

ErgenPac separates configured pacman repositories and Flathub results, shows user-facing installed applications, reports live operation progress with download speed, and refreshes package state automatically without blanking the current results. Third-party repositories configured in pacman, including Chaotic-AUR, are searched automatically.

## Features

- Combined pacman and Flatpak update view
- Hardware-aware Driver Manager for processor microcode and Intel, AMD or supported NVIDIA graphics
- Live search with exact-match ranking and category shortcuts
- Installed application view without core system package noise
- Transaction summary before package installation or removal
- Inline installation progress beside the selected package
- Aggregate update and driver download progress with safe cancellation before package deployment
- A centered restart action after a completed system update
- Friendly errors for offline repositories, locked databases, invalid signatures and low disk space
- Restricted polkit helper for privileged operations

Driver Manager uses packages from configured repositories and always shows the
proposed package list before authentication. Modern NVIDIA hardware uses the
official `nvidia-open-dkms` stack. Unknown or legacy NVIDIA generations are
flagged for manual review instead of receiving a potentially incompatible
driver. On systems configured with ErgenOS Secure Boot, DKMS driver
installation refreshes the signed boot components automatically.

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
