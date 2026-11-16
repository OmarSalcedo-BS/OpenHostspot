from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.direct_controller import DirectHotspotController
from core.network_manager import NetworkManager
from core.wifi_direct import (
    WiFiDirectAccessPoint, WiFiDirectAdvertisementPublisherStatus, WiFiDirectConnectionStatus,
)


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


def test_wifi_direct_tracks_connections_and_ignores_stale_disconnect():
    access_point = WiFiDirectAccessPoint()
    request = MagicMock()
    request.device_information = SimpleNamespace(id="peer", name="Teléfono")
    args = SimpleNamespace(get_connection_request=lambda: request)
    first = MagicMock(device_id="peer", connection_status=WiFiDirectConnectionStatus.CONNECTED)
    second = MagicMock(device_id="peer", connection_status=WiFiDirectConnectionStatus.CONNECTED)
    for device in (first, second):
        device.get_connection_endpoint_pairs.return_value = [
            SimpleNamespace(remote_host_name=SimpleNamespace(display_name="192.168.137.2"))
        ]

    async def connect(device_id):
        return devices.pop(0)

    devices = [first, second]
    with patch("core.wifi_direct.WiFiDirectDevice") as device_class, \
         patch("core.wifi_direct.comtypes.CoInitializeEx") as initialize, \
         patch("core.wifi_direct.comtypes.CoUninitialize"), \
         patch("core.wifi_direct.threading.Thread", side_effect=lambda target, daemon: SimpleNamespace(start=target)):
        device_class.from_id_async.side_effect = connect
        access_point._connection_requested(None, args)
        assert access_point.connected_devices() == [{"id": "peer", "name": "Teléfono", "ip": "192.168.137.2"}]
        assert access_point.take_device_events()[0]["kind"] == "connected"
        first_callback = first.add_connection_status_changed.call_args.args[0]
        access_point._connection_requested(None, args)
        assert access_point.take_device_events() == []
        first.connection_status = WiFiDirectConnectionStatus.DISCONNECTED
        first_callback(first, None)
        assert len(access_point.connected_devices()) == 1
        second.connection_status = WiFiDirectConnectionStatus.DISCONNECTED
        second.add_connection_status_changed.call_args.args[0](second, None)
        assert access_point.connected_devices() == []
        assert access_point.take_device_events()[0]["kind"] == "disconnected"
    initialize.assert_called_with(0)
    first.close.assert_called_once()
    second.close.assert_called_once()


def test_wifi_direct_connection_without_endpoint_is_still_tracked():
    access_point = WiFiDirectAccessPoint()
    request = MagicMock()
    request.device_information = SimpleNamespace(id="peer", name="")
    device = MagicMock(device_id="peer", connection_status=WiFiDirectConnectionStatus.CONNECTED)
    device.get_connection_endpoint_pairs.side_effect = OSError("IP pendiente")

    async def connect(device_id):
        return device

    with patch("core.wifi_direct.WiFiDirectDevice") as device_class, \
         patch("core.wifi_direct.comtypes.CoInitializeEx"), \
         patch("core.wifi_direct.comtypes.CoUninitialize"), \
         patch("core.wifi_direct.threading.Thread", side_effect=lambda target, daemon: SimpleNamespace(start=target)):
        device_class.from_id_async.side_effect = connect
        access_point._connection_requested(None, SimpleNamespace(get_connection_request=lambda: request))
    assert access_point.connected_devices() == [{"id": "peer", "name": "Dispositivo Wi-Fi", "ip": ""}]


def test_wifi_direct_reports_failed_connection_request():
    access_point = WiFiDirectAccessPoint()
    request = MagicMock()
    request.device_information = SimpleNamespace(id="peer", name="Teléfono")

    async def connect(device_id):
        raise OSError("conexión rechazada")

    with patch("core.wifi_direct.WiFiDirectDevice") as device_class, \
         patch("core.wifi_direct.comtypes.CoInitializeEx"), \
         patch("core.wifi_direct.comtypes.CoUninitialize"), \
         patch("core.wifi_direct.threading.Thread", side_effect=lambda target, daemon: SimpleNamespace(start=target)):
        device_class.from_id_async.side_effect = connect
        access_point._connection_requested(None, SimpleNamespace(get_connection_request=lambda: request))
    assert access_point.connected_devices() == []
    assert access_point.take_device_events() == [
        {"kind": "error", "name": "Teléfono", "error": "conexión rechazada"}
    ]
    request.close.assert_called_once()


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


def test_direct_controller_detects_adapter_without_internet_sharing():
    before = {"abc": adapter()}
    after = {"abc": adapter(up=True)}
    with patch("core.direct_controller.WiFiDirectAccessPoint") as network, \
         patch("core.direct_controller.ICSBridge") as bridge, \
         patch.object(NetworkManager, "is_admin", return_value=True), \
         patch("core.direct_controller._direct_adapters", side_effect=[before, after, after]), \
         patch("core.direct_controller.time.sleep"):
        network.return_value.start.return_value = {"success": True}
        network.return_value.status = "started"
        controller = DirectHotspotController("ssid", "password123", "")
        result = controller.start(enable_internet_sharing=False)
    assert result["success"] and not result["internet_shared"]
    assert controller.private_interface == "Virtual"
    assert controller.private_guid == "abc"
    bridge.return_value.enable_ics.assert_not_called()


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
