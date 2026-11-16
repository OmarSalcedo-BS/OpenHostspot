#!/usr/bin/env python3
"""
OpenHotspot - Aplicación para crear y gestionar un punto de acceso Wi-Fi en Windows.
Punto de entrada principal con interfaz CLI.
"""

import sys
import logging
import argparse
import time
from typing import Optional

from core.network_manager import NetworkManager
from core.ics_bridge import ICSBridge
from core.client_monitor import ClientMonitor
from core.hotspot_controller import HotspotController
from core.utils import ConsoleFormatter, ConfigValidator, FileHandler, SystemInfo, Logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CLIInterface:
    """Interfaz de línea de comandos para OpenHotspot."""
    
    def __init__(self):
        self.controller: Optional[HotspotController] = None
    
    def start_hotspot(self, ssid: str, password: str, public_if: str = "Ethernet") -> bool:
        """Inicia el hotspot."""
        print(ConsoleFormatter.header("Iniciando Hotspot"))
        
        # Validar credenciales
        valid_ssid, msg_ssid = ConfigValidator.validate_ssid(ssid)
        valid_pwd, msg_pwd = ConfigValidator.validate_password(password)
        
        if not valid_ssid:
            print(ConsoleFormatter.error(msg_ssid))
            return False
        
        if not valid_pwd:
            print(ConsoleFormatter.error(msg_pwd))
            return False
        
        # Crear controlador
        self.controller = HotspotController(ssid, password, public_if)
        
        # Iniciar
        result = self.controller.start(enable_internet_sharing=True)
        
        if result["success"]:
            print(ConsoleFormatter.success(result["message"]))
            if result.get("warning"):
                print(ConsoleFormatter.warning(f"Internet no compartido: {result['warning']}"))
            Logger.log_to_file(f"Hotspot iniciado: SSID={ssid}")
            
            # Mostrar QR
            print(ConsoleFormatter.info("Código QR para conectarse:"))
            self.controller.display_qr()
            
            # Modo interactivo
            self.interactive_mode()
            return True
        else:
            print(ConsoleFormatter.error(f"Error: {result.get('error', 'desconocido')}"))
            if "details" in result:
                for err in result["details"].get("errors", []):
                    print(f"  - {err}")
            return False
    
    def stop_hotspot(self) -> bool:
        """Detiene el hotspot."""
        if not self.controller:
            print(ConsoleFormatter.error("Hotspot no está activo"))
            return False
        
        result = self.controller.stop()
        if result["success"]:
            print(ConsoleFormatter.success(result["message"]))
            if result.get("warning"):
                print(ConsoleFormatter.warning(f"Revisa ICS: {result['warning']}"))
            Logger.log_to_file("Hotspot detenido")
            return True
        else:
            print(ConsoleFormatter.error(f"Error: {result.get('error')}"))
            if result.get("warning"):
                print(ConsoleFormatter.warning(f"Revisa ICS: {result['warning']}"))
            return False
    
    def show_status(self) -> None:
        """Muestra el estado del hotspot."""
        if not self.controller:
            print(ConsoleFormatter.warning("Hotspot no está activo"))
            return
        
        status = self.controller.get_status()
        stats = self.controller.get_statistics()
        
        print(ConsoleFormatter.header("Estado del Hotspot"))
        print(f"Estado: {ConsoleFormatter.success('EN LÍNEA') if status.is_running else ConsoleFormatter.error('FUERA DE LÍNEA')}")
        print(f"SSID: {status.ssid}")
        print(f"Clientes conectados: {status.clients_connected}")
        print(f"Compartición de internet: {ConsoleFormatter.success('ACTIVA') if status.internet_shared else ConsoleFormatter.warning('INACTIVA')}")
        
        if stats.get("clients_list"):
            print(ConsoleFormatter.info("Clientes activos:"))
            for client in stats["clients_list"]:
                print(f"  - {client.get('hostname', 'N/A'):20} | IP: {client.get('ip_address'):15} | MAC: {client.get('mac_address')}")
    
    def show_report(self) -> None:
        """Muestra reporte detallado del sistema."""
        if not self.controller:
            print(ConsoleFormatter.error("Hotspot no está activo"))
            return
        
        report = self.controller.get_detailed_report()
        
        print(ConsoleFormatter.header("Reporte Detallado del Sistema"))
        
        # Status
        status = report.get("status", {})
        print(ConsoleFormatter.info("Estado:"))
        print(f"  - Ejecutándose: {'Sí' if status.get('is_running') else 'No'}")
        print(f"  - SSID: {status.get('ssid')}")
        print(f"  - Clientes: {status.get('clients')}")
        print(f"  - Internet compartido: {'Sí' if status.get('internet_shared') else 'No'}")
        
        # Interfaces
        interfaces = report.get("interfaces", [])
        if interfaces:
            print(ConsoleFormatter.info("Interfaces de red:"))
            for iface in interfaces:
                print(f"  - {iface.get('name')}: {iface.get('type')} ({iface.get('status')})")
    
    def interactive_mode(self) -> None:
        """Modo interactivo para gestionar el hotspot."""
        print("\n" + ConsoleFormatter.info("Entrando en modo interactivo (escribe 'ayuda' para comandos)"))
        
        commands = {
            "status": ("Mostrar estado del hotspot", self.show_status),
            "clientes": ("Ver clientes conectados", self.show_status),
            "reporte": ("Mostrar reporte detallado", self.show_report),
            "qr": ("Mostrar código QR", lambda: self.controller.display_qr() if self.controller else None),
            "refrescar": ("Refrescar hotspot", lambda: self.refresh_hotspot()),
            "salir": ("Detener hotspot y salir", lambda: self.stop_hotspot()),
            "ayuda": ("Mostrar este mensaje", lambda: self.show_help(commands))
        }
        
        self.show_help(commands)
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd in commands:
                    commands[cmd][1]()
                elif cmd:
                    print(ConsoleFormatter.warning(f"Comando desconocido: {cmd}"))
                
                if cmd == "salir":
                    break
                    
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                print(ConsoleFormatter.error(f"Error: {e}"))
    
    def refresh_hotspot(self) -> bool:
        """Reinicia el hotspot."""
        if not self.controller:
            print(ConsoleFormatter.error("Hotspot no está activo"))
            return False
        
        print(ConsoleFormatter.info("Refrescando hotspot..."))
        result = self.controller.refresh()
        
        if result["success"]:
            print(ConsoleFormatter.success("Hotspot refrescado"))
            return True
        else:
            print(ConsoleFormatter.error(f"Error: {result.get('error')}"))
            return False
    
    @staticmethod
    def show_help(commands: dict) -> None:
        """Muestra la ayuda de comandos."""
        print(ConsoleFormatter.header("Comandos Disponibles"))
        for cmd, (desc, _) in commands.items():
            print(f"  {cmd:12} - {desc}")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="OpenHotspot - Crea un punto de acceso Wi-Fi en Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py --start --ssid "MiWifi" --password "12345678"  # Iniciar hotspot
  python main.py --status                                  # Ver estado
  python main.py --interfaces                              # Listar interfaces
        """
    )
    
    parser.add_argument("--start", action="store_true", help="Iniciar el hotspot")
    parser.add_argument("--stop", action="store_true", help="Detener el hotspot")
    parser.add_argument("--status", action="store_true", help="Mostrar estado del hotspot")
    parser.add_argument("--interfaces", action="store_true", help="Listar interfaces de red")
    parser.add_argument("--ssid", type=str, default="OpenHotspot", help="Nombre del hotspot (default: OpenHotspot)")
    parser.add_argument("--password", type=str, default="12345678", help="Contraseña del hotspot")
    parser.add_argument("--public-if", type=str, default="Ethernet", help="Interfaz pública (default: Ethernet)")
    parser.add_argument("--version", action="version", version="OpenHotspot 1.0.0")
    
    args = parser.parse_args()
    
    cli = CLIInterface()
    
    try:
        if args.start:
            return 0 if cli.start_hotspot(args.ssid, args.password, args.public_if) else 1
        
        elif args.stop:
            if cli.controller:
                cli.stop_hotspot()
            else:
                print(ConsoleFormatter.warning("Hotspot no está activo"))
        
        elif args.status:
            cli.show_status()
        
        elif args.interfaces:
            ics = ICSBridge()
            interfaces = ics.list_connections()
            print(ConsoleFormatter.header("Interfaces de Red Disponibles"))
            for iface in interfaces:
                print(f"  - {iface['name']}: {iface['type']} ({iface['status']})")
        
        else:
            print(ConsoleFormatter.header("OpenHotspot"))
            print("Usa --help para ver todas las opciones disponibles")
            print(f"Python: {SystemInfo.get_python_version()}")
            print(f"Plataforma: {SystemInfo.get_platform()}\n")
    
    except KeyboardInterrupt:
        print("\n" + ConsoleFormatter.warning("Operación cancelada por el usuario"))
        if cli.controller and cli.controller._is_fully_running:
            cli.stop_hotspot()
        sys.exit(0)
    
    except Exception as e:
        print(ConsoleFormatter.error(f"Error fatal: {e}"))
        logger.exception("Error no controlado")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
