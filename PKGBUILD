# Maintainer: Szymon Pilip <szymon.pilip@ergenos.dev>

pkgname=ergenpac
pkgver=1.0.1
pkgrel=2
pkgdesc='Graphical package manager and system updater for ErgenOS'
arch=('any')
url='https://github.com/ErgenosSW/ErgenPac'
license=('GPL-3.0-or-later')
depends=('ergenctl>=1.1.0.dev-9' 'fakeroot' 'flatpak' 'gtk4' 'libadwaita' 'pacman' 'pacman-contrib' 'pciutils' 'polkit' 'python' 'python-gobject')
makedepends=('meson')
_source_commit=89eb66b6a66a7c824dedf921ef10fd2b73d541a9
_source_dir="ErgenPac-${_source_commit}"
_source_commit=89eb66b6a66a7c824dedf921ef10fd2b73d541a9
_source_dir="ErgenPac-${_source_commit}"
source=("${pkgname}-${_source_commit}.tar.gz::${url}/archive/${_source_commit}.tar.gz")
sha256sums=('323cacf8ea29c56c3081b4f73f5f78385da5c6035821842eb6f46f93e5e53398')

build() {
  arch-meson "${_source_dir}" build
  meson compile -C build
}

check() {
  cd "${_source_dir}"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
}

package() {
  meson install -C build --destdir "${pkgdir}"
  install -Dm644 "${_source_dir}/LICENSE" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
