from unittest.mock import MagicMock, patch
import time

import pytest

from core.hotspot_controller import HotspotController
from core.ics_bridge import ICSBridge
from gui import OpenHotspotApp


@pytest.fixture
def app(tmp_path):
    from core.settings_store import SettingsStore

    with patch("gui.SettingsStore", return_value=SettingsStore(tmp_path / "settings.json")), \
         patch("gui.StartupManager") as startup, \
         patch("gui.SleepInhibitor") as power:
        startup.return_value.status.return_value = "disabled"
        window = OpenHotspotApp(auto_check=False)
        window.withdraw()
        window.update()
        yield window
        if not window._closed:
            window._finish_close()


def test_incompatible_adapter_blocks_real_start(app):
    app.password.set("password123")
    app._support = False
    with patch("gui.messagebox.showerror") as error, \
         patch("gui.DirectHotspotController") as controller:
        app._start()
        error.assert_called_once()
        controller.assert_not_called()
        assert not app._active


def test_gui_rejects_invalid_password(app):
    app.password.set("short")
    with patch("gui.messagebox.showerror") as error:
        app._start()
        error.assert_called_once()
        assert not app._active


def test_real_start_and_stop_run_through_controller(app):
    app.password.set("password123")
    app.public_interface.set("Ethernet")
    controller = MagicMock()
    controller.private_guid = ""
    controller.start.return_value = {"success": True, "internet_shared": False, "warning": "ICS rechazado"}
    controller.stop.return_value = {"success": True, "warning": None}

    def wait_for_operation():
        deadline = time.monotonic() + 5
        while app._busy and time.monotonic() < deadline:
            app.update()
            time.sleep(0.01)
        assert not app._busy

    with patch("gui.NetworkManager.is_admin", return_value=True), \
         patch("gui.DirectHotspotController", return_value=controller) as controller_class, \
         patch("gui.messagebox.showwarning") as warning:
        app._start()
        wait_for_operation()
        assert app._active
        app._power.set_active.assert_called_with(True)
        assert "internet no compartido" in app.hotspot_page.banner.cget("text")
        assert app.hotspot_page.qr_image is not None
        warning.assert_called_once()
        controller_class.assert_called_once_with("OpenHotspot", "password123", "Ethernet")
        controller.start.assert_called_once_with(enable_internet_sharing=True)
        app._stop()
        wait_for_operation()
        assert not app._active
        app._power.set_active.assert_called_with(False)
        assert app.hotspot_page.qr_image is None
        controller.stop.assert_called_once()


def test_gui_requests_elevation_with_current_interpreter():
    import gui
    with patch.object(gui.NetworkManager, "is_admin", return_value=False), \
         patch("gui.ctypes.windll.shell32.ShellExecuteW", return_value=33) as execute, \
         patch("gui.OpenHotspotApp") as app_class:
        assert gui.main() == 0
        assert execute.call_args.args[1] == "runas"
        assert execute.call_args.args[2] == gui.os.path.join(
            gui.os.path.dirname(gui.sys.executable), "pythonw.exe"
        )
        app_class.assert_not_called()


def test_cancelled_elevation_is_reported():
    import gui
    with patch.object(gui.NetworkManager, "is_admin", return_value=False), \
         patch("gui.ctypes.windll.shell32.ShellExecuteW", return_value=5), \
         patch("gui.messagebox.showerror") as error:
        assert gui.main() == 1
        error.assert_called_once()


def test_missing_pythonw_is_reported_instead_of_opening_console():
    import gui
    with patch.object(gui.NetworkManager, "is_admin", return_value=False), \
         patch("gui.os.path.isfile", return_value=False), \
         patch("gui.ctypes.windll.shell32.ShellExecuteW") as execute, \
         patch("gui.messagebox.showerror") as error:
        assert gui.main() == 1
        execute.assert_not_called()
        error.assert_called_once()


def test_settings_controls_are_real_and_follow_session_state(app):
    app._show_page("settings")
    assert app._current_page == "settings"
    assert app.settings_page.master is app.hotspot_page.master
    app.settings_page.password_switch.toggle()
    assert app.hotspot_page.password_entry.cget("show") == ""
    app.settings_page.share_switch.toggle()
    assert not app.share_internet.get()
    assert app.hotspot_page.public_box.cget("state") == "disabled"
    app._active = True
    app._update_controls()
    assert app.settings_page.share_switch.cget("state") == "disabled"


def test_navigation_transitions_remain_inside_main_window(app):
    app._show_page("settings")
    app._show_page("devices")
    app.update()
    assert app._current_page == "devices"
    assert app.devices_page.place_info()["relx"] == "0"
    assert app.devices_page.master.winfo_children()[-1] is app.devices_page
    assert app.settings_page.place_info()["relx"] == "0"


def test_confirmed_device_events_update_both_pages(app):
    app._active = True
    app._controller = MagicMock()
    network = app._controller.network
    network.connected_devices.return_value = [{"id": "peer", "name": "Teléfono", "ip": "192.168.137.2"}]
    network.take_device_events.return_value = [{"kind": "connected", "name": "Teléfono"}]
    app._tick_observer()
    assert "1 conexión" in app.hotspot_page.device_count.cget("text")
    assert "Se conectó: Teléfono" == app.hotspot_page.device_notice.cget("text")
    assert app.activity_notice.cget("text") == "Se conectó: Teléfono"
    assert "Se conectó: Teléfono" in app.devices_page._events[0]
    assert "Teléfono" in app.hotspot_page.device_list.winfo_children()[0].cget("text")
    assert "Teléfono" in app.devices_page.connected_frame.winfo_children()[0].cget("text")


def test_traffic_remains_visible_if_neighbor_query_fails(app):
    from concurrent.futures import Future

    rate = Future()
    rate.set_result({"sent_mbps": 0.02, "received_mbps": 2.0})
    app._show_traffic(rate)
    assert "20.0 Kbps" in app.hotspot_page.traffic_label.cget("text")
    assert "2.00 Mbps" in app.devices_page.traffic_label.cget("text")
    error = Future()
    error.set_exception(RuntimeError("sin vecinos"))
    app._show_observation(error)
    assert "20.0 Kbps" in app.hotspot_page.traffic_label.cget("text")
    assert "sin vecinos" in app.devices_page.clients_status.cget("text")


def test_preferences_do_not_save_partially_edited_network(app):
    app.ssid.set("Red guardada")
    app.password.set("password123")
    app.public_interface.set("Ethernet")
    app._save_network_settings()
    app.ssid.set("Edición pendiente")
    app.password.set("incompleta")
    app.show_qr.set(False)
    app.speed_unit.set("Mbps")
    app._visual_changed()
    saved = app._settings_store.load()
    assert (saved.ssid, saved.password, saved.public_interface) == ("Red guardada", "password123", "Ethernet")
    assert not saved.show_qr and saved.speed_unit == "Mbps"


def test_saved_settings_are_loaded_and_password_stays_hidden(tmp_path):
    from core.settings_store import AppSettings, SettingsStore

    store = SettingsStore(tmp_path / "settings.json")
    store.save(AppSettings(ssid="Mi red", password="password123", public_interface="Ethernet",
                           prevent_sleep=False, show_qr=False, speed_unit="Mbps"))
    with patch("gui.SettingsStore", return_value=store), \
         patch("gui.StartupManager") as startup, patch("gui.SleepInhibitor"):
        startup.return_value.status.return_value = "disabled"
        window = OpenHotspotApp(auto_check=False)
        try:
            window.withdraw()
            assert (window.ssid.get(), window.password.get(), window.public_interface.get()) == (
                "Mi red", "password123", "Ethernet")
            assert window.hotspot_page.password_entry.cget("show") == "*"
            assert not window.prevent_sleep.get() and not window.show_qr.get()
            assert window.speed_unit.get() == "Mbps"
        finally:
            window._finish_close()


def test_corrupt_settings_are_not_overwritten(app):
    app._settings_available = False
    app._settings_store.path.write_text("corrupto", encoding="utf-8")
    with patch("gui.messagebox.showerror") as error:
        app._save_network_settings()
    error.assert_called_once()
    assert app._settings_store.path.read_text(encoding="utf-8") == "corrupto"


def test_startup_error_restores_switch(app):
    app._startup.set_enabled.side_effect = PermissionError("denegado")
    app.start_with_windows.set(True)
    with patch("gui.messagebox.showerror") as error:
        app._change_startup()
    assert not app.start_with_windows.get()
    assert "denegado" in app.settings_page.startup_status.cget("text")
    error.assert_called_once()


def test_display_preferences_hide_notices_and_restore_qr(app):
    from concurrent.futures import Future
    from core.network_manager import NetworkManager

    app._active = True
    app._current_qr = NetworkManager("red", "password123").generate_wifi_qr()["qr"]
    app.show_qr.set(False)
    app.show_device_notices.set(False)
    app.speed_unit.set("Mbps")
    app._visual_changed()
    assert app.hotspot_page.qr_image is None
    app._controller = MagicMock()
    app._controller.network.connected_devices.return_value = []
    app._controller.network.take_device_events.return_value = [{"kind": "connected", "name": "Teléfono"}]
    app._tick_observer()
    assert app.hotspot_page.device_notice.cget("text") == ""
    assert "Teléfono" in app.devices_page._events[-1]
    rate = Future()
    rate.set_result({"sent_mbps": 0.02, "received_mbps": 2.0})
    app._show_traffic(rate)
    assert "0.02 Mbps" in app.hotspot_page.traffic_label.cget("text")
    app.show_qr.set(True)
    app._visual_changed()
    assert app.hotspot_page.qr_image is not None


def test_power_follows_active_and_aborted_state(app):
    app._apply_power()
    app._power.set_active.assert_called_with(False)
    app._active = True
    app._apply_power()
    app._power.set_active.assert_called_with(True)
    app._abort_reported = True
    app._apply_power()
    app._power.set_active.assert_called_with(False)
    app._abort_reported = False
    app._power.set_active.side_effect = OSError("denegado")
    with patch("gui.messagebox.showwarning") as warning:
        app._apply_power()
    assert "denegado" in app.settings_page.power_status.cget("text")
    warning.assert_called_once()
    app._power.set_active.side_effect = None


def test_speed_test_runs_without_blocking_hotspot_controls(app):
    def wait_for_result():
        deadline = time.monotonic() + 5
        while app._speed_pending and time.monotonic() < deadline:
            app.update()
            time.sleep(0.01)
        assert not app._speed_pending

    with patch("gui.measure_speed", return_value={"download_mbps": 42.0, "upload_mbps": 12.0}):
        app._run_speed_test()
        assert not app._busy
        wait_for_result()
    assert "42.00 Mbps" in app.devices_page.speed_label.cget("text")
    assert "12.00 Mbps" in app.devices_page.speed_label.cget("text")
    assert app.devices_page.speed_button.cget("state") == "normal"


def make_bridge(public_sharing=False, private_failure=None):
    public, private = object(), object()
    public_config, private_config = MagicMock(), MagicMock()
    public_config.SharingEnabled = public_sharing
    private_config.SharingEnabled = False
    if private_failure:
        private_config.EnableSharing.side_effect = private_failure
    share = MagicMock()
    share.EnumEveryConnection = [public, private]
    share.NetConnectionProps.side_effect = lambda conn: MagicMock(Name="Ethernet" if conn is public else "Virtual")
    share.INetSharingConfigurationForINetConnection.side_effect = lambda conn: (
        public_config if conn is public else private_config
    )
    bridge = ICSBridge.__new__(ICSBridge)
    bridge.net_share = share
    return bridge, public_config, private_config


def test_ics_does_not_replace_existing_sharing():
    bridge, public_config, private_config = make_bridge(public_sharing=True)
    with patch.object(bridge, "is_admin", return_value=True):
        result = bridge.enable_ics("Ethernet", "Virtual")
    assert not result["success"]
    assert "ya está activo" in result["error"]
    public_config.EnableSharing.assert_not_called()
    private_config.EnableSharing.assert_not_called()


def test_ics_rolls_back_public_interface_if_private_fails():
    bridge, public_config, private_config = make_bridge(private_failure=RuntimeError("fallo"))
    with patch.object(bridge, "is_admin", return_value=True):
        result = bridge.enable_ics("Ethernet", "Virtual")
    assert not result["success"]
    assert "fallo" in result["error"]
    public_config.EnableSharing.assert_called_once_with(0)
    public_config.DisableSharing.assert_called_once()
    private_config.EnableSharing.assert_called_once_with(1)


def test_ics_rejects_private_adapter_guid_mismatch():
    bridge, public_config, private_config = make_bridge()
    with patch.object(bridge, "is_admin", return_value=True):
        result = bridge.enable_ics("Ethernet", "Virtual", private_connection_guid="abc")
    assert not result["success"]
    assert "GUID" in result["error"]
    public_config.EnableSharing.assert_not_called()
    private_config.EnableSharing.assert_not_called()


def test_ics_accepts_matching_private_adapter_guid():
    bridge, public_config, private_config = make_bridge()
    bridge.net_share.NetConnectionProps.side_effect = lambda conn: MagicMock(
        Name="Ethernet" if conn is bridge.net_share.EnumEveryConnection[0] else "Virtual",
        Guid="{ABC}",
    )
    with patch.object(bridge, "is_admin", return_value=True):
        result = bridge.enable_ics("Ethernet", "Virtual", private_connection_guid="abc")
    assert result["success"]
    public_config.EnableSharing.assert_called_once_with(0)
    private_config.EnableSharing.assert_called_once_with(1)


def test_controller_reports_ics_failure_without_claiming_internet():
    with patch("core.hotspot_controller.ICSBridge") as bridge_class, \
         patch("core.hotspot_controller.time.sleep"):
        controller = HotspotController("ssid", "password123", "Ethernet", "Virtual")
        controller.network_manager.is_admin = MagicMock(return_value=True)
        controller.network_manager.start_hosted_network = MagicMock(return_value={"success": True})
        controller.client_monitor.start_monitoring = MagicMock()
        bridge_class.return_value.enable_ics.return_value = {"success": False, "error": "ICS rechazado"}
        result = controller.start()
    assert result["success"]
    assert result["internet_shared"] is False
    assert result["warning"] == "ICS rechazado"


def test_controller_stops_only_ics_it_enabled():
    with patch("core.hotspot_controller.ICSBridge") as bridge_class:
        controller = HotspotController("ssid", "password123", "Ethernet", "Virtual")
        controller.client_monitor.stop_monitoring = MagicMock()
        controller.network_manager.stop_hosted_network = MagicMock(return_value={"success": True})
        controller.stop()
        bridge_class.return_value.disable_ics.assert_not_called()
        controller._ics_enabled = True
        bridge_class.return_value.disable_ics.return_value = {"success": True}
        result = controller.stop()
    assert result["success"]
    assert [call.args[0] for call in bridge_class.return_value.disable_ics.call_args_list] == [
        "Virtual", "Ethernet"
    ]


def test_qr_escapes_wifi_delimiters():
    from core.network_manager import NetworkManager

    result = NetworkManager("A;B", 'pass:word"123').generate_wifi_qr()
    assert result["success"]
    assert result["qr"].data_list[0].data == b'WIFI:S:A\\;B;T:WPA;P:pass\\:word\\"123;;'
