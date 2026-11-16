import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.hotspot_observer import HotspotObserver, TrafficMonitor
from core import speed_test


GUID = "f914a53a-ffe3-43d7-b56d-512edf1ecb5c"


def test_observer_scopes_and_filters_neighbors():
    response = {
        "Name": "Virtual",
        "Neighbors": [
            {"IP": "192.168.137.2", "MAC": "02:00:00:00:00:01", "State": "Reachable"},
            {"IP": "224.0.0.1", "MAC": "01-00-5E-00-00-01", "State": "Permanent"},
            {"IP": "192.168.137.3", "MAC": "00-00-00-00-00-00", "State": "Stale"},
        ],
    }
    with patch("core.hotspot_observer.subprocess.run") as run:
        run.return_value.stdout = json.dumps(response)
        result = HotspotObserver(GUID).snapshot()
    assert result["neighbors"] == [{"ip": "192.168.137.2", "mac": "02-00-00-00-00-01",
                                    "state": "Reachable"}]
    command = run.call_args.args[0][-1]
    assert "[guid]$_.InterfaceGuid" in command
    assert "InterfaceIndex -eq $adapter.ifIndex" in command


def test_traffic_is_sampled_independently_of_neighbors():
    counters = [
        {"Virtual": SimpleNamespace(bytes_sent=100, bytes_recv=200)},
        {"Virtual": SimpleNamespace(bytes_sent=1000100, bytes_recv=500200)},
        {"Virtual": SimpleNamespace(bytes_sent=10, bytes_recv=20)},
    ]
    with patch("core.hotspot_observer.psutil.net_io_counters", side_effect=counters), \
         patch("core.hotspot_observer.time.monotonic", side_effect=[10, 12, 13]):
        monitor = TrafficMonitor("Virtual")
        assert monitor.sample() is None
        assert monitor.sample() == {"sent_mbps": 4.0, "received_mbps": 2.0}
        assert monitor.sample() is None


def test_traffic_does_not_invent_zero_for_missing_counters():
    with patch("core.hotspot_observer.psutil.net_io_counters", return_value={}):
        with pytest.raises(RuntimeError, match="No hay contadores"):
            TrafficMonitor("Virtual").sample()


def test_observer_rejects_malformed_guid():
    with pytest.raises(ValueError):
        HotspotObserver("not-a-guid")


@pytest.fixture
def speed_server(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        received = 0
        short_download = False

        def do_GET(self):
            payload = b"x" * (4095 if self.short_download else 4096)
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            type(self).received = len(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(204)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(speed_test, "DOWNLOAD_URL", base + "/down")
    monkeypatch.setattr(speed_test, "UPLOAD_URL", base + "/up")
    monkeypatch.setattr(speed_test, "DOWNLOAD_BYTES", 4096)
    monkeypatch.setattr(speed_test, "UPLOAD_BYTES", 2048)
    yield Handler
    server.shutdown()
    server.server_close()
    thread.join()


def test_speed_test_transfers_data_and_returns_measured_rates(speed_server):
    result = speed_test.measure_speed()
    assert result["download_mbps"] > 0
    assert result["upload_mbps"] > 0
    assert speed_server.received == 2048


def test_speed_test_rejects_incomplete_download(speed_server):
    speed_server.short_download = True
    with pytest.raises(RuntimeError, match="Descarga incompleta"):
        speed_test.measure_speed()
    assert speed_server.received == 0
