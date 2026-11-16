import pytest
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.network_manager import NetworkManager
from core.ics_bridge import ICSBridge
from core.client_monitor import ClientMonitor


class TestNetworkManager:
    """Tests para NetworkManager"""

    @pytest.mark.parametrize("stdout,stderr,expected", [
        ("No se pudo iniciar la red hospedada.", "", "No se pudo iniciar la red hospedada."),
        ("", "Acceso denegado.", "Acceso denegado."),
        ("", "", "código 1"),
    ])
    def test_start_reports_netsh_failure(self, stdout, stderr, expected):
        manager = NetworkManager("TestSSID", "TestPassword123")
        failure = subprocess.CalledProcessError(
            1, ["netsh", "wlan", "start", "hostednetwork"],
            output=stdout, stderr=stderr
        )
        with patch.object(manager, "is_admin", return_value=True), \
             patch("core.network_manager.subprocess.run", side_effect=[
                 subprocess.CompletedProcess([], 0, stdout="Configurado", stderr=""),
                 failure,
             ]):
            result = manager.start_hosted_network()
        assert result["success"] is False
        assert expected in result["error"]

    @pytest.mark.parametrize("output,expected", [
        ("Red hospedada admitida: no", False),
        ("Red hospedada admitida: Sí", True),
        ("Hosted network supported : No", False),
        ("Hosted network supported : Yes", True),
        ("Otro idioma", None),
    ])
    def test_hosted_network_support(self, output, expected):
        assert NetworkManager._parse_hosted_network_support(output) is expected
    
    def test_init(self):
        """Test inicialización de NetworkManager"""
        nm = NetworkManager("TestSSID", "TestPassword123")
        assert nm.ssid == "TestSSID"
        assert nm.password == "TestPassword123"
        assert nm.is_running is False

    def test_validate_credentials_valid(self):
        """Test validación de credenciales válidas"""
        nm = NetworkManager("ValidSSID", "ValidPass123")
        result = nm.validate_credentials()
        assert result["success"] is True

    def test_validate_credentials_empty_ssid(self):
        """Test validación de SSID vacío"""
        nm = NetworkManager("", "ValidPass123")
        result = nm.validate_credentials()
        assert result["success"] is False
        assert any("SSID" in error for error in result["errors"])

    def test_validate_credentials_short_password(self):
        """Test validación de contraseña corta"""
        nm = NetworkManager("TestSSID", "Short12")
        result = nm.validate_credentials()
        assert result["success"] is False
        assert any("mínimo 8" in error for error in result["errors"])

    def test_set_credentials(self):
        """Test actualizar credenciales"""
        nm = NetworkManager("OldSSID", "OldPassword123")
        result = nm.set_credentials("NewSSID", "NewPassword123")
        assert result["success"] is True
        assert nm.ssid == "NewSSID"
        assert nm.password == "NewPassword123"

    def test_is_admin(self):
        """Test verificación de admin (debería fallar en test)"""
        result = NetworkManager.is_admin()
        # En ambiente de test, probablemente no sea admin, puede retornar False o 0
        assert result in (True, False, 0, 1)


class TestICSBridge:
    """Tests para ICSBridge"""
    
    def test_init(self):
        """Test inicialización de ICSBridge"""
        bridge = ICSBridge()
        assert bridge is not None

    def test_is_admin(self):
        """Test verificación de admin"""
        result = ICSBridge.is_admin()
        # En ambiente de test, puede retornar False o 0
        assert result in (True, False, 0, 1)

    def test_list_connections(self):
        """Test listar conexiones"""
        bridge = ICSBridge()
        connections = bridge.list_connections()
        assert isinstance(connections, list)

    def test_get_connection_type(self):
        """Test identificación de tipo de conexión"""
        bridge = ICSBridge()
        ethernet = bridge._get_connection_type(0)
        assert ethernet == "ethernet"
        
        wifi = bridge._get_connection_type(6)
        assert wifi == "wireless"
        
        unknown = bridge._get_connection_type(999)
        assert unknown == "unknown"


class TestClientMonitor:
    """Tests para ClientMonitor"""
    
    def test_init(self):
        """Test inicialización de ClientMonitor"""
        monitor = ClientMonitor()
        assert monitor.clients == {}
        assert monitor.monitoring is False

    def test_get_client_count_empty(self):
        """Test conteo de clientes vacío"""
        monitor = ClientMonitor()
        assert monitor.get_client_count() == 0

    def test_get_clients_empty(self):
        """Test obtener clientes vacío"""
        monitor = ClientMonitor()
        clients = monitor.get_clients()
        assert clients == []

    def test_disconnect_client_not_found(self):
        """Test desconectar cliente que no existe"""
        monitor = ClientMonitor()
        result = monitor.disconnect_client("00:00:00:00:00:00")
        assert result["success"] is False
        assert "no encontrado" in result["error"]

    def test_disconnect_client_does_not_claim_to_disconnect_a_known_client(self):
        monitor = ClientMonitor()
        monitor.clients["00:00:00:00:00:00"] = MagicMock()
        result = monitor.disconnect_client("00:00:00:00:00:00")
        assert not result["success"]
        assert "no está disponible" in result["error"]
        assert "00:00:00:00:00:00" in monitor.clients

    def test_start_stop_monitoring(self):
        """Test iniciar y detener monitoreo"""
        monitor = ClientMonitor()
        monitor.start_monitoring()
        assert monitor.monitoring is True
        monitor.stop_monitoring()
        assert monitor.monitoring is False

    def test_get_statistics_empty(self):
        """Test obtener estadísticas sin clientes"""
        monitor = ClientMonitor()
        stats = monitor.get_statistics()
        assert stats["total_clients"] == 0
        assert "interface_stats" in stats

    def test_export_clients_json_empty(self):
        """Test exportar clientes a JSON cuando está vacío"""
        monitor = ClientMonitor()
        json_str = monitor.export_clients_json()
        assert json_str == "[]"


class TestIntegration:
    """Tests de integración"""
    
    def test_hotspot_controller_imports(self):
        """Test que se pueden importar todos los módulos"""
        from main import HotspotController
        assert HotspotController is not None

    def test_hotspot_controller_initialization(self):
        """Test inicialización del controlador"""
        from main import HotspotController
        controller = HotspotController("TestSSID", "TestPassword123")
        assert controller.ssid == "TestSSID"
        assert controller.password == "TestPassword123"
        assert isinstance(controller.network_manager, NetworkManager)
        assert isinstance(controller.ics_bridge, ICSBridge)
        assert isinstance(controller.client_monitor, ClientMonitor)

    def test_cli_starts_only_once_and_propagates_failure(self, capsys):
        import main
        with patch.object(sys, "argv", ["main.py", "--start"]), \
             patch.object(main.CLIInterface, "start_hotspot", return_value=False) as start:
            assert main.main() == 1
            start.assert_called_once()

    def test_main_entry_point_help_does_not_offer_demo(self):
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [sys.executable, os.path.join(project_dir, "main.py"), "--help"],
            cwd=project_dir, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30
        )
        assert result.returncode == 0
        assert "--demo" not in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
