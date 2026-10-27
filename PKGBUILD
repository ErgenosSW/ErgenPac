# Maintainer: Szymon Pilip <szymon.pilip@ergenos.dev>

pkgname=ergenpac
pkgver=1.0.1
pkgrel=1
pkgdesc='Graphical package manager and system updater for ErgenOS'
arch=('any')
url='https://github.com/ErgenosSW/ErgenPac'
license=('GPL-3.0-or-later')
depends=('ergenctl>=1.1.0.dev-9' 'fakeroot' 'flatpak' 'gtk4' 'libadwaita' 'pacman' 'pacman-contrib' 'pciutils' 'polkit' 'python' 'python-gobject')
makedepends=('meson')
source=("${pkgname}-${pkgver}.tar.gz::https://github.com/ErgenosSW/ErgenPac/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('c30b16e1b4c1a36a2bf6fac719a29c8f4004be0c8e276cc3b54f7d7fbbb8a2e7')

build() {
  arch-meson "ErgenPac-${pkgver}" build
  meson compile -C build
}

check() {
  cd "ErgenPac-${pkgver}"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
}

package() {
  meson install -C build --destdir "${pkgdir}"
  install -Dm644 "ErgenPac-${pkgver}/LICENSE" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
