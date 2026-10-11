project('ergenpac', version: '0.2.2', meson_version: '>=1.3.0')

python = import('python').find_installation('python3')

python.install_sources(
  files(
    'src/ergenpac/__init__.py',
    'src/ergenpac/app.py',
    'src/ergenpac/core.py',
  ),
  subdir: 'ergenpac',
)

launcher = configuration_data()
launcher.set('PYTHON', python.full_path())
configure_file(
  input: 'data/ergenpac.in',
  output: 'ergenpac',
  configuration: launcher,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_data(
  'src/ergenpac/helper.py',
  install_dir: get_option('libdir') / 'ergenpac',
  rename: 'ergenpac-helper',
  install_mode: 'rwxr-xr-x',
)
install_data(
  'data/io.github.ergenossw.ErgenPac.desktop',
  install_dir: get_option('datadir') / 'applications',
)
install_data(
  'data/io.github.ergenossw.ErgenPac.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)
install_data(
  'data/io.github.ergenossw.ErgenPac.policy',
  install_dir: get_option('datadir') / 'polkit-1' / 'actions',
)
install_data(
  'data/icons/hicolor/512x512/apps/io.github.ergenossw.ErgenPac.png',
  install_dir: get_option('datadir') / 'icons' / 'hicolor' / '512x512' / 'apps',
)
