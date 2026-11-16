import psutil
import subprocess
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ClientInfo:
    """Información detallada de un cliente conectado."""
    mac_address: str
    ip_address: str
    hostname: Optional[str]
    signal_strength: Optional[int]
    connection_time: str
    rx_bytes: int
    tx_bytes: int
    last_activity: str


class ClientMonitor:
    """
    Monitorea los clientes conectados al punto de acceso Wi-Fi,
    rastreando conexiones, uso de ancho de banda y actividad de red.
    """

    def __init__(self, virtual_interface_name: str = "microsoft_hosted_network") -> None:
        """
        Inicializa el monitor de clientes.
        
        Args:
            virtual_interface_name: Nombre de la interfaz virtual del hotspot.
        """
        self.virtual_interface_name: str = virtual_interface_name
        self.clients: Dict[str, ClientInfo] = {}
        self.monitoring: bool = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.data_lock = threading.Lock()

    def _get_arp_table(self) -> List[Dict[str, str]]:
        """
        Obtiene la tabla ARP (Address Resolution Protocol) del sistema.
        
        Returns:
            list: Lista de diccionarios con información de las conexiones ARP.
        """
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                check=True
            )
            
            arp_entries: List[Dict[str, str]] = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines:
                line = line.strip()
                if not line or "Interface" in line or "---" in line:
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    arp_entries.append({
                        "ip": parts[0],
                        "mac": parts[1],
                        "type": parts[2] if len(parts) > 2 else "unknown"
                    })
            
            return arp_entries
        except subprocess.CalledProcessError as e:
            print(f"Error obteniendo tabla ARP: {e}")
            return []

    def _get_hostname(self, ip_address: str) -> Optional[str]:
        """
        Resuelve el nombre de host de una dirección IP.
        
        Args:
            ip_address: Dirección IP del cliente.
            
        Returns:
            Nombre del host o None si no se puede resolver.
        """
        try:
            import socket
            hostname = socket.gethostbyaddr(ip_address)[0]
            return hostname
        except (socket.herror, socket.error):
            return None

    def _get_netstat_connections(self) -> List[Dict[str, Any]]:
        """
        Obtiene las conexiones activas usando netstat.
        
        Returns:
            list: Lista de conexiones de red activas.
        """
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                check=True
            )
            
            connections: List[Dict[str, Any]] = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[4:]:  # Saltar encabezados
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        connections.append({
                            "proto": parts[0],
                            "local": parts[1],
                            "remote": parts[2],
                            "state": parts[3],
                            "pid": int(parts[4])
                        })
                    except (ValueError, IndexError):
                        continue
            
            return connections
        except subprocess.CalledProcessError as e:
            print(f"Error obteniendo netstat: {e}")
            return []

    def _get_interface_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la interfaz virtual.
        
        Returns:
            dict: Estadísticas de bytes enviados/recibidos y paquetes.
        """
        try:
            if_addrs = psutil.net_if_stats()
            
            if self.virtual_interface_name in if_addrs:
                stats = if_addrs[self.virtual_interface_name]
                return {
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "packets_sent": stats.packets_sent,
                    "packets_recv": stats.packets_recv,
                    "is_up": stats.isup
                }
            return {}
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {}

    def scan_clients(self) -> Dict[str, ClientInfo]:
        """
        Realiza un escaneo de los clientes conectados actualmente.
        
        Returns:
            dict: Diccionario con información de clientes (MAC -> ClientInfo).
        """
        arp_table = self._get_arp_table()
        current_time = datetime.now().isoformat()
        
        with self.data_lock:
            for entry in arp_table:
                mac = entry["mac"].upper()
                ip = entry["ip"]
                
                if mac not in self.clients:
                    hostname = self._get_hostname(ip)
                    self.clients[mac] = ClientInfo(
                        mac_address=mac,
                        ip_address=ip,
                        hostname=hostname,
                        signal_strength=None,
                        connection_time=current_time,
                        rx_bytes=0,
                        tx_bytes=0,
                        last_activity=current_time
                    )
                else:
                    self.clients[mac].last_activity = current_time
                    self.clients[mac].ip_address = ip
            
            return self.clients.copy()

    def get_clients(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de clientes conectados como diccionarios.
        
        Returns:
            list: Lista de clientes con su información.
        """
        with self.data_lock:
            return [asdict(client) for client in self.clients.values()]

    def get_client_count(self) -> int:
        """
        Retorna la cantidad total de clientes conectados.
        
        Returns:
            int: Número de clientes.
        """
        with self.data_lock:
            return len(self.clients)

    def disconnect_client(self, mac_address: str) -> Dict[str, Any]:
        """
        Intenta desconectar un cliente específico (si es soportado).
        
        Args:
            mac_address: Dirección MAC del cliente a desconectar.
            
        Returns:
            dict: Estado de la operación.
        """
        with self.data_lock:
            if mac_address not in self.clients:
                return {"success": False, "error": f"Cliente {mac_address} no encontrado."}
            return {"success": False, "error": "La desconexión de clientes no está disponible."}

    def start_monitoring(self, interval: int = 5) -> None:
        """
        Inicia el monitoreo automático de clientes en segundo plano.
        
        Args:
            interval: Intervalo en segundos entre escaneos.
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Detiene el monitoreo automático de clientes."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def _monitor_loop(self, interval: int) -> None:
        """
        Bucle interno del monitoreo.
        
        Args:
            interval: Tiempo en segundos entre escaneos.
        """
        while self.monitoring:
            try:
                self.scan_clients()
                time.sleep(interval)
            except Exception as e:
                print(f"Error en bucle de monitoreo: {e}")
                time.sleep(interval)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales del monitoreo.
        
        Returns:
            dict: Estadísticas incluyendo cantidad de clientes, actividad, etc.
        """
        with self.data_lock:
            if not self.clients:
                return {
                    "total_clients": 0,
                    "interface_stats": self._get_interface_stats(),
                    "uptime": "N/A"
                }
            
            total_rx = sum(c.rx_bytes for c in self.clients.values())
            total_tx = sum(c.tx_bytes for c in self.clients.values())
            
            return {
                "total_clients": len(self.clients),
                "total_rx_bytes": total_rx,
                "total_tx_bytes": total_tx,
                "interface_stats": self._get_interface_stats(),
                "clients_list": [asdict(c) for c in self.clients.values()]
            }

    def export_clients_json(self) -> str:
        """
        Exporta la información de clientes en formato JSON.
        
        Returns:
            str: JSON string con la información de clientes.
        """
        import json
        with self.data_lock:
            return json.dumps([asdict(c) for c in self.clients.values()], indent=2)

    def get_client_by_mac(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de un cliente específico.
        
        Args:
            mac_address: Dirección MAC del cliente.
            
        Returns:
            dict: Información del cliente o None si no existe.
        """
        mac_upper = mac_address.upper()
        with self.data_lock:
            if mac_upper in self.clients:
                return asdict(self.clients[mac_upper])
            return None

    def get_clients_by_activity(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Obtiene clientes activos en los últimos N minutos.
        
        Args:
            minutes: Minutos de actividad a considerar.
            
        Returns:
            list: Clientes activos.
        """
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        with self.data_lock:
            active_clients = []
            for client in self.clients.values():
                try:
                    last_activity = datetime.fromisoformat(client.last_activity)
                    if last_activity > cutoff_time:
                        active_clients.append(asdict(client))
                except (ValueError, TypeError):
                    pass
            return active_clients

    def get_bandwidth_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de ancho de banda.
        
        Returns:
            dict: Estadísticas totales y por cliente.
        """
        with self.data_lock:
            if not self.clients:
                return {"total_rx": 0, "total_tx": 0, "by_client": []}
            
            by_client = []
            total_rx = 0
            total_tx = 0
            
            for client in self.clients.values():
                total_rx += client.rx_bytes
                total_tx += client.tx_bytes
                by_client.append({
                    "mac": client.mac_address,
                    "hostname": client.hostname,
                    "rx_mb": round(client.rx_bytes / (1024**2), 2),
                    "tx_mb": round(client.tx_bytes / (1024**2), 2)
                })
            
            return {
                "total_rx_mb": round(total_rx / (1024**2), 2),
                "total_tx_mb": round(total_tx / (1024**2), 2),
                "by_client": sorted(by_client, key=lambda x: x["rx_mb"] + x["tx_mb"], reverse=True)
            }

    def clear_clients(self) -> None:
        """Limpia la lista de clientes monitoreados."""
        with self.data_lock:
            self.clients.clear()

    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Obtiene estado detallado del monitoreo.
        
        Returns:
            dict: Estado completo incluyendo clientes, estad y estadísticas.
        """
        with self.data_lock:
            return {
                "monitoring_active": self.monitoring,
                "total_clients": len(self.clients),
                "clients": [asdict(c) for c in self.clients.values()],
                "statistics": self.get_statistics(),
                "bandwidth": self.get_bandwidth_stats()
            }
