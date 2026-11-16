import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from core.settings_store import AppSettings, SettingsError, SettingsStore
from core.windows_integration import SleepInhibitor, StartupManager


def test_settings_round_trip_protects_password(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.load() == AppSettings()
    settings = AppSettings(ssid="Mi red", password="secreto123", public_interface="Ethernet",
                           show_qr=False, speed_unit="Mbps")
    store.save(settings)
    assert "secreto123" not in store.path.read_text(encoding="utf-8")
    assert store.load() == settings


@pytest.mark.parametrize("contents", [
    "{",
    '{"version": 2}',
    '{"version": 1, "show_qr": "true"}',
    '{"version": 1, "password_dpapi": "no es base64"}',
])
def test_invalid_settings_are_reported_without_replacement(tmp_path, contents):
    path = tmp_path / "settings.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(SettingsError):
        SettingsStore(path).load()
    assert path.read_text(encoding="utf-8") == contents


def test_dpapi_failure_is_reported(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "password_dpapi": "YQ=="}), encoding="utf-8")
    with patch("core.settings_store.win32crypt.CryptUnprotectData", side_effect=ValueError("error")):
        with pytest.raises(SettingsError, match="descifrar"):
            SettingsStore(path).load()


def test_save_failure_preserves_existing_file(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.save(AppSettings(password="password123"))
    original = store.path.read_bytes()
    with patch("core.settings_store.os.replace", side_effect=PermissionError("denegado")):
        with pytest.raises(SettingsError, match="denegado"):
            store.save(AppSettings(password="another123"))
    assert store.path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_startup_changes_only_own_entry(tmp_path):
    script = tmp_path / "gui.pyw"
    pythonw = tmp_path / "pythonw.exe"
    script.touch()
    pythonw.touch()
    manager = StartupManager(script)
    manager.pythonw = pythonw
    registry = {}
    key = MagicMock()
    key.__enter__.return_value = key

    def query(*args):
        if not registry:
            raise FileNotFoundError()
        return registry["value"], registry["kind"]

    def set_value(key, name, reserved, kind, value):
        registry.update(value=value, kind=kind)

    with patch("core.windows_integration.winreg.OpenKey", return_value=key), \
         patch("core.windows_integration.winreg.CreateKeyEx", return_value=key), \
         patch("core.windows_integration.winreg.QueryValueEx", side_effect=query), \
         patch("core.windows_integration.winreg.SetValueEx", side_effect=set_value) as set_entry, \
         patch("core.windows_integration.winreg.DeleteValue", side_effect=lambda *args: registry.clear()) as delete:
        assert manager.status() == "disabled"
        manager.set_enabled(True)
        assert manager.status() == "enabled"
        manager.set_enabled(False)
        assert manager.status() == "disabled"
        delete.assert_called_once()
        registry.update(value="other application", kind=1)
        with pytest.raises(RuntimeError, match="diferente"):
            manager.set_enabled(True)
        with pytest.raises(RuntimeError, match="diferente"):
            manager.set_enabled(False)
        assert set_entry.call_count == 1
        assert delete.call_count == 1


def test_startup_registry_error_propagates(tmp_path):
    manager = StartupManager(tmp_path / "gui.pyw")
    with patch("core.windows_integration.winreg.OpenKey", side_effect=PermissionError("denegado")):
        with pytest.raises(PermissionError, match="denegado"):
            manager.set_enabled(True)


def test_sleep_inhibitor_requires_same_thread_and_releases():
    inhibitor = SleepInhibitor()
    function = MagicMock(return_value=1)
    kernel = MagicMock(SetThreadExecutionState=function)
    errors = []
    with patch("core.windows_integration.ctypes.WinDLL", return_value=kernel):
        inhibitor.set_active(True)
        thread = threading.Thread(target=lambda: _release_in_thread(inhibitor, errors))
        thread.start()
        thread.join()
        assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
        inhibitor.set_active(False)
    assert [call.args[0] for call in function.call_args_list] == [
        inhibitor.ES_CONTINUOUS | inhibitor.ES_SYSTEM_REQUIRED, inhibitor.ES_CONTINUOUS,
    ]


def _release_in_thread(inhibitor, errors):
    try:
        inhibitor.set_active(False)
    except RuntimeError as error:
        errors.append(error)


def test_sleep_inhibitor_reports_windows_failure():
    inhibitor = SleepInhibitor()
    kernel = MagicMock(SetThreadExecutionState=MagicMock(return_value=0))
    with patch("core.windows_integration.ctypes.WinDLL", return_value=kernel):
        with pytest.raises(OSError):
            inhibitor.set_active(True)
    assert not inhibitor._active
