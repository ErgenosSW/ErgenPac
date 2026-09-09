# Maintainer: ErgenOS Project <https://github.com/ErgenosSW>

pkgname=ergenpac
pkgver=0.2.1
pkgrel=1
pkgdesc='Graphical package manager and system updater for ErgenOS'
arch=('any')
url='https://github.com/ErgenosSW/ErgenPac'
license=('GPL-3.0-or-later')
depends=('flatpak' 'gtk4' 'libadwaita' 'pacman' 'pacman-contrib' 'pciutils' 'polkit' 'python' 'python-gobject')
makedepends=('meson')
source=("${pkgname}-${pkgver}.tar.gz::https://github.com/ErgenosSW/ErgenPac/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

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
