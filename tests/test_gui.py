from unittest.mock import MagicMock, patch
import time

import pytest

from core.hotspot_controller import HotspotController
from core.ics_bridge import ICSBridge
from gui import OpenHotspotApp


@pytest.fixture
def app():
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
        assert "internet no compartido" in app.hotspot_page.banner.cget("text")
        warning.assert_called_once()
        controller_class.assert_called_once_with("OpenHotspot", "password123", "Ethernet")
        controller.start.assert_called_once_with(enable_internet_sharing=True)
        app._stop()
        wait_for_operation()
        assert not app._active
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
    deadline = time.monotonic() + 2
    while app._transition_id is not None and time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    assert app._transition_id is None
    assert app._current_page == "devices"
    assert app.devices_page.place_info()["relx"] == "0"
    assert not app.settings_page.place_info()


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
