"""
Orquestador principal del sistema OpenHotspot.
Gestiona NetworkManager, ICSBridge y ClientMonitor como un sistema unificado.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .network_manager import NetworkManager
from .ics_bridge import ICSBridge
from .client_monitor import ClientMonitor


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class HotspotStatus:
    """Estado agregado del hotspot."""
    is_running: bool
    ssid: str
    clients_connected: int
    internet_shared: bool
    error_message: Optional[str] = None


class HotspotController:
    """
    Controlador unificado para gestionar el ciclo de vida completo del hotspot.
    Integra NetworkManager, ICSBridge y ClientMonitor en una interfaz coherente.
    """

    def __init__(
        self, 
        ssid: str, 
        password: str,
        public_interface: str = "Ethernet",
        private_interface: str = "Local Area Connection* 1",
        monitor_interval: int = 5
    ):
        """
        Inicializa el controlador del hotspot.
        
        Args:
            ssid: Nombre del punto de acceso.
            password: Contraseña del hotspot.
            public_interface: Interfaz con acceso a internet (Ethernet/Wi-Fi).
            private_interface: Interfaz virtual del hotspot.
            monitor_interval: Intervalo de monitoreo en segundos.
        """
        self.ssid = ssid
        self.password = password
        self.public_interface = public_interface
        self.private_interface = private_interface
        self.monitor_interval = monitor_interval
        
        self.network_manager = NetworkManager(ssid, password)
        self.ics_bridge = ICSBridge()
        self.client_monitor = ClientMonitor(private_interface)
        
        self._is_fully_running = False
        self._ics_enabled = False
        logger.info(f"HotspotController inicializado para SSID: {ssid}")

    def start(self, enable_internet_sharing: bool = True) -> Dict[str, Any]:
        """
        Inicia el hotspot completo con todas sus funcionalidades.
        
        Args:
            enable_internet_sharing: Si True, habilita ICS automáticamente.
            
        Returns:
            dict: Estado de la inicialización.
        """
        logger.info("Iniciando hotspot...")
        
        # 1. Validar credenciales
        validation = self.network_manager.validate_credentials()
        if not validation["success"]:
            logger.error(f"Validación fallida: {validation}")
            return {"success": False, "error": "Credenciales inválidas", "details": validation}
        
        # 2. Verificar privilegios
        if not self.network_manager.is_admin():
            logger.error("Se requieren privilegios de administrador")
            return {"success": False, "error": "Se requieren privilegios de administrador"}
        
        # 3. Iniciar red hospedada
        start_result = self.network_manager.start_hosted_network()
        if not start_result["success"]:
            logger.error(f"Error iniciando red hospedada: {start_result}")
            return start_result
        
        logger.info("Red hospedada iniciada")
        time.sleep(2)
        
        # 4. Habilitar ICS si se solicita
        ics_warning = None
        if enable_internet_sharing:
            ics_result = self.ics_bridge.enable_ics(
                self.public_interface,
                self.private_interface
            )
            
            if not ics_result["success"]:
                logger.warning(f"ICS no se pudo habilitar: {ics_result['error']}")
                ics_warning = ics_result["error"]
            else:
                self._ics_enabled = True
                logger.info("ICS habilitado exitosamente")
                time.sleep(2)
        
        # 5. Iniciar monitoreo de clientes
        self.client_monitor.start_monitoring(self.monitor_interval)
        logger.info(f"Monitoreo de clientes iniciado (intervalo: {self.monitor_interval}s)")
        
        self._is_fully_running = True
        logger.info("Hotspot iniciado")
        
        return {
            "success": True,
            "message": f"Hotspot '{self.ssid}' iniciado correctamente",
            "ssid": self.ssid,
            "password_hidden": "***" + self.password[-3:],
            "monitoring": True,
            "internet_shared": self._ics_enabled,
            "warning": ics_warning
        }

    def stop(self, disable_internet_sharing: bool = True) -> Dict[str, Any]:
        """
        Detiene el hotspot completamente.
        
        Args:
            disable_internet_sharing: Si True, deshabilita ICS.
            
        Returns:
            dict: Estado de la detención.
        """
        logger.info("Deteniendo hotspot...")
        
        # 1. Detener monitoreo
        self.client_monitor.stop_monitoring()
        logger.info("Monitoreo de clientes detenido")
        
        # 2. Deshabilitar ICS
        ics_errors = []
        if disable_internet_sharing and self._ics_enabled:
            for interface in (self.private_interface, self.public_interface):
                ics_result = self.ics_bridge.disable_ics(interface)
                if not ics_result["success"]:
                    ics_errors.append(ics_result.get("error", f"Error al desactivar ICS en {interface}"))
            if not ics_errors:
                self._ics_enabled = False
        
        # 3. Detener red hospedada
        stop_result = self.network_manager.stop_hosted_network()
        if not stop_result["success"]:
            logger.error(f"Error deteniendo red: {stop_result}")
            if ics_errors:
                stop_result["warning"] = "; ".join(ics_errors)
            return stop_result
        
        self._is_fully_running = False
        logger.info("Hotspot detenido")
        
        return {
            "success": True,
            "message": "Hotspot detenido correctamente",
            "clients_recorded": self.client_monitor.get_client_count(),
            "warning": "; ".join(ics_errors) if ics_errors else None
        }

    def get_status(self) -> HotspotStatus:
        """
        Obtiene el estado actual del hotspot.
        
        Returns:
            HotspotStatus: Estado agregado.
        """
        network_status = self.network_manager.get_hosted_network_status()
        ics_status = self.ics_bridge.get_ics_status(self.private_interface)
        
        is_running = network_status.get("success", False) and \
                     network_status.get("data", {}).get("status") == "started"
        
        internet_shared = ics_status.get("success", False) and \
                         ics_status.get("sharing_enabled", False)
        
        clients_count = self.client_monitor.get_client_count()
        
        return HotspotStatus(
            is_running=is_running,
            ssid=self.ssid,
            clients_connected=clients_count,
            internet_shared=internet_shared,
            error_message=None if is_running else "Hotspot no está activo"
        )

    def refresh(self) -> Dict[str, Any]:
        """
        Reinicia el hotspot sin perder la configuración.
        
        Returns:
            dict: Estado de la operación.
        """
        logger.info("Refrescando hotspot...")
        
        stop_result = self.stop(disable_internet_sharing=True)
        if not stop_result["success"]:
            return stop_result
        
        time.sleep(3)
        
        return self.start(enable_internet_sharing=True)

    def generate_qr(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera un código QR para conectarse al hotspot.
        
        Args:
            output_path: Ruta para guardar la imagen QR.
            
        Returns:
            dict: Resultado con el QR.
        """
        return self.network_manager.generate_wifi_qr(output_path)

    def display_qr(self) -> Dict[str, Any]:
        """Muestra el código QR en la consola."""
        return self.network_manager.display_wifi_qr()

    def get_clients(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de clientes conectados.
        
        Returns:
            list: Lista de clientes con información detallada.
        """
        return self.client_monitor.get_clients()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas completas del sistema.
        
        Returns:
            dict: Estadísticas de clientes, ancho de banda, etc.
        """
        return self.client_monitor.get_statistics()

    def list_available_interfaces(self) -> List[Dict[str, Any]]:
        """
        Lista las interfaces de red disponibles.
        
        Returns:
            list: Interfaces detectadas.
        """
        return self.ics_bridge.list_connections()

    def disconnect_client(self, mac_address: str) -> Dict[str, Any]:
        """
        Desconecta un cliente específico.
        
        Args:
            mac_address: MAC address del cliente.
            
        Returns:
            dict: Estado de la operación.
        """
        return self.client_monitor.disconnect_client(mac_address)

    def update_credentials(self, ssid: str, password: str) -> Dict[str, Any]:
        """
        Actualiza SSID y contraseña (requiere reiniciar hotspot).
        
        Args:
            ssid: Nuevo SSID.
            password: Nueva contraseña.
            
        Returns:
            dict: Resultado de validación.
        """
        self.ssid = ssid
        self.password = password
        self.network_manager.set_credentials(ssid, password)
        return self.network_manager.validate_credentials()

    def test_connection(self, target_url: str = "https://www.google.com") -> Dict[str, Any]:
        """
        Prueba la conexión a internet a través del hotspot.
        
        Args:
            target_url: URL para probar.
            
        Returns:
            dict: Resultado de la prueba.
        """
        try:
            import requests
            response = requests.get(target_url, timeout=5)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "url": target_url
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": target_url
            }

    def get_detailed_report(self) -> Dict[str, Any]:
        """
        Genera un reporte detallado del sistema.
        
        Returns:
            dict: Reporte completo.
        """
        status = self.get_status()
        stats = self.get_statistics()
        interfaces = self.list_available_interfaces()
        
        return {
            "status": {
                "is_running": status.is_running,
                "ssid": status.ssid,
                "clients": status.clients_connected,
                "internet_shared": status.internet_shared
            },
            "statistics": stats,
            "interfaces": interfaces,
            "network_info": self.network_manager.show_network_info()
        }
