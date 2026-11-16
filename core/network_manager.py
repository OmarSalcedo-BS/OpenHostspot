import subprocess
import sys
import ctypes
import qrcode
import logging
from typing import Dict, Any, Optional, List
from qrcode.image.pure import PyPNGImage


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NetworkManager:
    """
    Gestiona el ciclo de vida del punto de acceso Wi-Fi (SoftAP) en Windows
    y la generación de credenciales visuales para dispositivos móviles.
    """
    
    def __init__(self, ssid: str, password: str) -> None:
        self.ssid: str = ssid
        self.password: str = password
        self.is_running: bool = False

    @staticmethod
    def _netsh_encoding() -> Optional[str]:
        if sys.platform == "win32":
            code_page = ctypes.windll.kernel32.GetConsoleOutputCP()
            return f"cp{code_page}" if code_page else "oem"
        return None

    @staticmethod
    def _parse_hosted_network_support(output: str) -> Optional[bool]:
        statuses = []
        for line in output.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip().casefold() in (
                "red hospedada admitida", "hosted network supported"
            ):
                value = value.strip().casefold()
                statuses.append(True if value in ("sí", "si", "yes") else
                                False if value == "no" else None)
        if True in statuses:
            return True
        if statuses and all(status is False for status in statuses):
            return False
        return None

    @staticmethod
    def _parse_wifi_direct_support(output: str) -> Optional[bool]:
        statuses = []
        for line in output.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip().casefold() == "wi-fi direct go":
                value = value.strip().casefold()
                statuses.append(True if value in ("compatible", "supported") else
                                False if value in ("no compatible", "not supported") else None)
        if True in statuses:
            return True
        if statuses and all(status is False for status in statuses):
            return False
        return None

    @classmethod
    def get_wifi_direct_support(cls) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "wirelesscapabilities"],
                capture_output=True, text=True, encoding=cls._netsh_encoding(),
                errors="replace", check=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return {"success": True, "supported": cls._parse_wifi_direct_support(result.stdout)}
        except subprocess.CalledProcessError as error:
            return {"success": False, "error": cls._command_error(error)}
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"success": False, "error": str(error)}

    @staticmethod
    def _command_error(error: subprocess.CalledProcessError) -> str:
        details = "\n".join(part.strip() for part in (error.stdout, error.stderr)
                            if part and part.strip())
        return details or f"netsh falló con código {error.returncode}, sin mensaje."

    @staticmethod
    def is_admin() -> bool:
        """
        Verifica si el proceso actual cuenta con privilegios de Administrador,
        necesarios para alterar configuraciones de adaptadores de red en Windows.
        
        Returns:
            bool: True si es administrador, False en caso contrario.
        """
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    def validate_credentials(self) -> Dict[str, Any]:
        """
        Valida que las credenciales de SSID y contraseña sean válidas.
        
        Returns:
            dict: Resultado de validación con success y errores si aplica.
        """
        errors = []
        
        if not self.ssid:
            errors.append("SSID no puede estar vacío")
        elif len(self.ssid) > 32:
            errors.append("SSID no puede exceder 32 caracteres")
        
        if not self.password:
            errors.append("Contraseña no puede estar vacía")
        elif len(self.password) < 8:
            errors.append("Contraseña debe tener mínimo 8 caracteres")
        elif len(self.password) > 63:
            errors.append("Contraseña no puede exceder 63 caracteres")
        
        if errors:
            return {"success": False, "errors": errors}
        
        return {"success": True}

    def start_hosted_network(self) -> Dict[str, Any]:
        """
        Configura los parámetros de la red hospedada (SSID y WPA2) e intenta iniciarla.
        
        Returns:
            dict: Diccionario con el estado de éxito ('success') y mensaje o error.
        """
        if not self.is_admin():
            return {"success": False, "error": "Se requieren privilegios de Administrador."}

        validation = self.validate_credentials()
        if not validation["success"]:
            return validation

        try:
            logger.info(f"Iniciando red hospedada: SSID={self.ssid}")
            
            # 1. Configurar SSID y clave de seguridad
            config_res = subprocess.run(
                ["netsh", "wlan", "set", "hostednetwork", "mode=allow", f"ssid={self.ssid}", f"key={self.password}"],
                capture_output=True, text=True, encoding=self._netsh_encoding(),
                errors="replace", check=True
            )
            logger.info(f"Configuración: {config_res.stdout.strip()}")
            
            # 2. Iniciar el servicio de red hospedada
            start_res = subprocess.run(
                ["netsh", "wlan", "start", "hostednetwork"],
                capture_output=True, text=True, encoding=self._netsh_encoding(),
                errors="replace", check=True
            )
            
            if "already" not in start_res.stdout.lower() and start_res.returncode == 0:
                self.is_running = True
            
            logger.info(f"Red hospedada iniciada: {start_res.stdout.strip()}")
            return {"success": True, "output": start_res.stdout.strip()}
        
        except subprocess.CalledProcessError as e:
            message = self._command_error(e)
            logger.error("Error al iniciar red hospedada: %s", message)
            return {"success": False, "error": message}
        except OSError as e:
            logger.error("No se pudo ejecutar netsh: %s", e)
            return {"success": False, "error": f"No se pudo ejecutar netsh: {e}"}

    def stop_hosted_network(self) -> Dict[str, Any]:
        """
        Detiene la transmisión de la red hospedada.
        
        Returns:
            dict: Estado de la operación.
        """
        try:
            logger.info("Deteniendo red hospedada...")
            stop_res = subprocess.run(
                ["netsh", "wlan", "stop", "hostednetwork"],
                capture_output=True, text=True, check=True
            )
            self.is_running = False
            logger.info(f"Red hospedada detenida: {stop_res.stdout.strip()}")
            return {"success": True, "output": stop_res.stdout.strip()}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al detener red hospedada: {e.stderr}")
            return {"success": False, "error": e.stderr.strip()}

    def refresh_hosted_network(self) -> Dict[str, Any]:
        """
        Reinicia la red hospedada sin perder la configuración.
        
        Returns:
            dict: Estado de la operación.
        """
        stop_result = self.stop_hosted_network()
        if not stop_result["success"]:
            return stop_result
        
        import time
        time.sleep(2)
        
        return self.start_hosted_network()

    def get_hosted_network_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual de la red hospedada.
        
        Returns:
            dict: Información del estado de la red hospedada.
        """
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "hostednetwork"],
                capture_output=True, text=True, check=True
            )
            
            output = result.stdout
            status_info = {
                "status": "unknown",
                "ssid": None,
                "clients_connected": 0
            }
            
            for line in output.split("\n"):
                line = line.strip()
                if "Status" in line:
                    if "Started" in line:
                        status_info["status"] = "started"
                    elif "Stopped" in line:
                        status_info["status"] = "stopped"
                elif "SSID" in line and ":" in line:
                    status_info["ssid"] = line.split(":", 1)[1].strip()
                elif "Number of clients" in line and ":" in line:
                    try:
                        status_info["clients_connected"] = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
            
            return {"success": True, "data": status_info}
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Error obteniendo estado: {e.stderr}")
            return {"success": False, "error": e.stderr.strip()}

    def generate_wifi_qr(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera una matriz QR codificada con el estándar universal de conexión Wi-Fi.
        
        Args:
            output_path: Ruta opcional para guardar la imagen QR en PNG.
        
        Returns:
            dict: Diccionario con el objeto QR y ruta si se guardó.
        """
        try:
            def escape(value: str) -> str:
                for character in ("\\", ";", ",", ":", '"'):
                    value = value.replace(character, "\\" + character)
                return value

            wifi_string: str = f"WIFI:S:{escape(self.ssid)};T:WPA;P:{escape(self.password)};;"
            qr = qrcode.QRCode(version=1, box_size=2, border=1)
            qr.add_data(wifi_string)
            qr.make(fit=True)
            
            if output_path:
                qr.make_image().save(output_path)
                logger.info(f"Código QR guardado en: {output_path}")
                return {"success": True, "qr": qr, "saved_to": output_path}
            
            return {"success": True, "qr": qr}
        
        except Exception as e:
            logger.error(f"Error generando QR: {e}")
            return {"success": False, "error": str(e)}

    def display_wifi_qr(self) -> Dict[str, Any]:
        """
        Muestra el código QR en la consola en formato ASCII.
        
        Returns:
            dict: Estado de la operación.
        """
        try:
            qr_result = self.generate_wifi_qr()
            if not qr_result["success"]:
                return qr_result
            
            qr = qr_result["qr"]
            qr.print_ascii(invert=True)
            return {"success": True, "message": "QR mostrado en consola"}
        
        except Exception as e:
            logger.error(f"Error mostrando QR: {e}")
            return {"success": False, "error": str(e)}

    def set_credentials(self, ssid: str, password: str) -> Dict[str, Any]:
        """
        Actualiza las credenciales de la red hospedada.
        
        Args:
            ssid: Nuevo nombre de red.
            password: Nueva contraseña.
            
        Returns:
            dict: Resultado de validación y actualización.
        """
        self.ssid = ssid
        self.password = password
        return self.validate_credentials()

    def show_network_info(self) -> Dict[str, Any]:
        """
        Muestra información detallada de la red hospedada.
        
        Returns:
            dict: Información de la red.
        """
        status = self.get_hosted_network_status()
        if not status["success"]:
            return status
        
        info = {
            "ssid": self.ssid,
            "password": "***" + self.password[-3:],
            "status": status["data"],
            "is_admin": self.is_admin()
        }
        
        return {"success": True, "info": info}

    def list_available_channels(self) -> Dict[str, Any]:
        """
        Lista los canales Wi-Fi disponibles.
        
        Returns:
            dict: Información de canales disponibles.
        """
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "drivers"],
                capture_output=True, text=True, check=True
            )
            
            channels = []
            for line in result.stdout.split("\n"):
                if "channel" in line.lower():
                    channels.append(line.strip())
            
            return {"success": True, "channels": channels}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": str(e)}

    def get_security_info(self) -> Dict[str, Any]:
        """
        Obtiene información de seguridad de la red.
        
        Returns:
            dict: Información de seguridad (protocolo, cifrado, etc).
        """
        return {
            "success": True,
            "security": {
                "protocol": "WPA2",
                "encryption": "CCMP (AES)",
                "auth_method": "PSK",
                "min_password_length": 8,
                "max_password_length": 63
            }
        }

    def export_configuration(self) -> Dict[str, Any]:
        """
        Exporta la configuración actual.
        
        Returns:
            dict: Configuración exportada.
        """
        return {
            "ssid": self.ssid,
            "password": self.password,
            "is_running": self.is_running,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

    def validate_system_requirements(self) -> Dict[str, Any]:
        """
        Valida que el sistema cumpla los requisitos para ejecutar hotspot.
        
        Returns:
            dict: Resultado de validación.
        """
        requirements = {"admin": bool(self.is_admin()), "netsh_available": False,
                        "wlan_driver": None}
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "drivers"],
                capture_output=True, text=True, encoding=self._netsh_encoding(),
                errors="replace", check=True, timeout=5
            )
            requirements["netsh_available"] = True
            requirements["wlan_driver"] = self._parse_hosted_network_support(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error("No se pudieron consultar los controladores Wi-Fi: %s",
                         self._command_error(e))
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.error("No se pudo ejecutar la consulta de controladores Wi-Fi: %s", e)

        requirements_met = all(value is True for value in requirements.values())
        
        return {
            "success": requirements_met,
            "requirements": requirements,
            "message": "Sistema cumple requisitos" if requirements_met else "El sistema no cumple algunos requisitos"
        }