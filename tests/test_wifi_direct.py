from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.direct_controller import DirectHotspotController
from core.network_manager import NetworkManager
from core.wifi_direct import WiFiDirectAccessPoint, WiFiDirectAdvertisementPublisherStatus


@pytest.mark.parametrize("line,expected", [
    ("Wi-Fi Direct GO : compatible", True),
    ("Wi-Fi Direct GO : no compatible", False),
    ("Wi-Fi Direct GO : Supported", True),
    ("Wi-Fi Direct GO : Not supported", False),
    ("Controlador desconocido", None),
])
def test_wifi_direct_capability_parser(line, expected):
    assert NetworkManager._parse_wifi_direct_support(line) is expected


def test_wifi_direct_starts_and_stops_on_confirmed_events():
    publisher = MagicMock()
    listener = MagicMock()
    callbacks = {}
    publisher.add_status_changed.side_effect = lambda callback: callbacks.setdefault("status", callback)
    publisher.start.side_effect = lambda: callbacks["status"](
        publisher, SimpleNamespace(status=WiFiDirectAdvertisementPublisherStatus.STARTED)
    )
    publisher.stop.side_effect = lambda: callbacks["status"](
        publisher, SimpleNamespace(status=WiFiDirectAdvertisementPublisherStatus.STOPPED)
    )
    with patch("core.wifi_direct.WiFiDirectAdvertisementPublisher", return_value=publisher), \
         patch("core.wifi_direct.WiFiDirectConnectionListener", return_value=listener):
        access_point = WiFiDirectAccessPoint()
        assert access_point.start("ssid", "password123")["success"]
        assert access_point.status == "started"
        assert publisher.advertisement.legacy_settings.ssid == "ssid"
        assert access_point.stop()["success"]
        assert access_point.status == "stopped"
        listener.remove_connection_requested.assert_called_once()
        publisher.remove_status_changed.assert_called_once()


def test_wifi_direct_does_not_claim_success_when_start_aborts():
    publisher = MagicMock()
    callback = {}
    publisher.add_status_changed.side_effect = lambda handler: callback.setdefault("status", handler)
    publisher.start.side_effect = lambda: callback["status"](
        publisher, SimpleNamespace(status=WiFiDirectAdvertisementPublisherStatus.ABORTED,
                                   error=SimpleNamespace(name="RADIO_NOT_AVAILABLE"))
    )
    with patch("core.wifi_direct.WiFiDirectAdvertisementPublisher", return_value=publisher), \
         patch("core.wifi_direct.WiFiDirectConnectionListener"):
        access_point = WiFiDirectAccessPoint()
        result = access_point.start("ssid", "password123")
    assert not result["success"]
    assert "RADIO_NOT_AVAILABLE" in result["error"]
    publisher.stop.assert_called_once()


def adapter(name="Virtual", up=False):
    return {"Name": name, "Guid": "{ABC}", "Up": up}


def test_direct_controller_only_enables_ics_on_activated_adapter():
    before = {"abc": adapter()}
    after = {"abc": adapter(up=True)}
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", side_effect=[before, after, after]), \
         patch("core.direct_controller.time.sleep"):
        network.return_value.start.return_value = {"success": True}
        network.return_value.status = "started"
        bridge.return_value.enable_ics.return_value = {"success": True}
        controller = DirectHotspotController("ssid", "password123", "Ethernet")
        result = controller.start()
    assert result["success"] and result["internet_shared"]
    bridge.return_value.enable_ics.assert_called_once_with(
        "Ethernet", "Virtual", private_connection_guid="abc"
    )


def test_direct_controller_refuses_an_already_active_adapter():
    stats = {"abc": adapter(up=True)}
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", return_value=stats):
        controller = DirectHotspotController("ssid", "password123", "Ethernet")
        result = controller.start()
    assert not result["success"]
    network.return_value.start.assert_not_called()
    bridge.return_value.enable_ics.assert_not_called()


def test_direct_controller_reports_adapter_lookup_failure_after_start():
    stats = {"abc": adapter()}
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", side_effect=[stats, RuntimeError("sin acceso")]):
        network.return_value.start.return_value = {"success": True}
        network.return_value.status = "started"
        controller = DirectHotspotController("ssid", "password123", "Ethernet")
        result = controller.start()
    assert result["success"]
    assert not result["internet_shared"]
    assert "sin acceso" in result["warning"]
    bridge.return_value.enable_ics.assert_not_called()


@pytest.mark.parametrize("snapshots", [
    [{}, {}],
    [{"abc": adapter(up=True), "def": adapter("Otro", up=True)}],
    [{"abc": adapter(up=True)}, {"def": adapter("Otro", up=True)}],
])
def test_direct_controller_does_not_share_when_detection_is_ambiguous(snapshots):
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", side_effect=[{}] + snapshots), \
         patch("core.direct_controller.time.monotonic", side_effect=[0, 9]), \
         patch("core.direct_controller.time.sleep"):
        network.return_value.start.return_value = {"success": True}
        network.return_value.status = "started"
        result = DirectHotspotController("ssid", "password123", "Ethernet").start()
    assert result["success"] and not result["internet_shared"]
    assert result["warning"]
    bridge.return_value.enable_ics.assert_not_called()


def test_direct_controller_does_not_share_if_publisher_aborts_during_detection():
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", return_value={}), \
         patch("core.direct_controller.time.sleep"):
        network.return_value.start.return_value = {"success": True}
        network.return_value.status = "aborted"
        result = DirectHotspotController("ssid", "password123", "Ethernet").start()
    assert result["success"] and not result["internet_shared"]
    assert "dejó de estar activa" in result["warning"]
    bridge.return_value.enable_ics.assert_not_called()


def test_direct_controller_fails_before_start_when_enumeration_fails():
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge"), \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", side_effect=RuntimeError("sin acceso")):
        result = DirectHotspotController("ssid", "password123", "Ethernet").start()
    assert not result["success"] and "sin acceso" in result["error"]
    network.return_value.start.assert_not_called()


def test_adapter_enumeration_checks_windows_response():
    from core.direct_controller import _direct_adapters

    with patch("core.direct_controller.subprocess.run") as run:
        run.return_value.stdout = '[{"Name":"Virtual","Guid":"{ABC}","Up":true}]'
        assert _direct_adapters() == {"abc": adapter(up=True)}
        run.return_value.stdout = '[{"Name":"Virtual","Guid":"{ABC}"}]'
        with pytest.raises(RuntimeError, match="datos incompletos"):
            _direct_adapters()
