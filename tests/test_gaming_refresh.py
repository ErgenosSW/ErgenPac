"""Exercise the async catalog flow without opening a window or contacting mirrors."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from ergenpac.app import ErgenPacWindow


class GamingRefreshTests(TestCase):
    def window(self):
        return SimpleNamespace(
            _gaming_database=None, _gaming_catalog_warning='',
            gaming_status=Mock(), _run=Mock(), _gaming_catalog_synced=Mock(),
            _gaming_available_loaded=Mock(), _gaming_flatpaks_loaded=Mock(),
        )

    def test_refresh_uses_private_database_not_system_sync(self):
        window = self.window()
        ErgenPacWindow._gaming_native_loaded(window, 0, '', '')
        try:
            arguments = window._run.call_args.args[0]
            self.assertEqual(arguments[0], 'env')
            self.assertEqual(arguments[-1], 'checkupdates')
            self.assertEqual(arguments[1], 'CHECKUPDATES_DB=' + window._gaming_database.name)
            self.assertNotIn('/var/lib/pacman', arguments[1])
        finally:
            window._gaming_database.cleanup()

    def test_no_updates_is_a_successful_catalog_refresh(self):
        for status in (0, 2):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                window = self.window()
                window._gaming_database = SimpleNamespace(name=directory)
                ErgenPacWindow._gaming_catalog_synced(window, status, '', '')
                self.assertEqual(window._run.call_args.args[0], ['pacman', '--dbpath', directory, '-Sl'])

    def test_offline_refresh_marks_cached_results(self):
        window = self.window()
        ErgenPacWindow._gaming_catalog_synced(window, 1, '', 'network unavailable')
        self.assertIn('cached', window._gaming_catalog_warning)
        self.assertEqual(window._run.call_args.args[0], ['pacman', '-Sl'])

    def test_fresh_multilib_catalog_finds_steam_and_cleans_up(self):
        window = self.window()
        window._gaming_database = tempfile.TemporaryDirectory()
        directory = Path(window._gaming_database.name)
        ErgenPacWindow._gaming_available_loaded(window, 0, 'multilib steam 1.0.0.87-3\n', '')
        self.assertIn('steam', window._gaming_available)
        self.assertFalse(directory.exists())
        self.assertIsNone(window._gaming_database)

    def test_failed_lookup_is_not_silently_treated_as_missing_packages(self):
        window = self.window()
        ErgenPacWindow._gaming_available_loaded(window, 1, '', 'missing databases')
        self.assertTrue(window._gaming_catalog_warning)
        self.assertEqual(window._gaming_available, set())

    def test_navigation_during_updates_queues_catalog_refresh(self):
        window = SimpleNamespace(_busy=True, _gaming_refresh_pending=False)
        ErgenPacWindow._refresh_gaming(window)
        self.assertTrue(window._gaming_refresh_pending)
