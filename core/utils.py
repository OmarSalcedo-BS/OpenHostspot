"""
Utilidades y herramientas auxiliares para OpenHotspot.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional


class ConsoleFormatter:
    """Utilidades para formatear salida en consola."""
    
    # Detectar si estamos en Windows y ajustar símbolos
    IS_WINDOWS = sys.platform.startswith('win')
    
    # Colores ANSI (compatibles con Windows 10+)
    COLORS = {
        'RESET': '' if IS_WINDOWS else '\033[0m',
        'BOLD': '' if IS_WINDOWS else '\033[1m',
        'GREEN': '' if IS_WINDOWS else '\033[92m',
        'RED': '' if IS_WINDOWS else '\033[91m',
        'YELLOW': '' if IS_WINDOWS else '\033[93m',
        'BLUE': '' if IS_WINDOWS else '\033[94m',
        'CYAN': '' if IS_WINDOWS else '\033[96m'
    }
    
    # Símbolos compatibles con Windows
    SYMBOLS = {
        'success': '[OK]' if IS_WINDOWS else '✓',
        'error': '[ERROR]' if IS_WINDOWS else '✗',
        'warning': '[WARNING]' if IS_WINDOWS else '⚠',
        'info': '[INFO]' if IS_WINDOWS else 'ℹ'
    }
    
    @staticmethod
    def success(message: str) -> str:
        """Formatea un mensaje de éxito."""
        return f"{ConsoleFormatter.COLORS['GREEN']}{ConsoleFormatter.SYMBOLS['success']} {message}{ConsoleFormatter.COLORS['RESET']}"
    
    @staticmethod
    def error(message: str) -> str:
        """Formatea un mensaje de error."""
        return f"{ConsoleFormatter.COLORS['RED']}{ConsoleFormatter.SYMBOLS['error']} {message}{ConsoleFormatter.COLORS['RESET']}"
    
    @staticmethod
    def warning(message: str) -> str:
        """Formatea un mensaje de advertencia."""
        return f"{ConsoleFormatter.COLORS['YELLOW']}{ConsoleFormatter.SYMBOLS['warning']} {message}{ConsoleFormatter.COLORS['RESET']}"
    
    @staticmethod
    def info(message: str) -> str:
        """Formatea un mensaje informativo."""
        return f"{ConsoleFormatter.COLORS['CYAN']}{ConsoleFormatter.SYMBOLS['info']} {message}{ConsoleFormatter.COLORS['RESET']}"
    
    @staticmethod
    def header(message: str) -> str:
        """Formatea un encabezado."""
        return f"\n{ConsoleFormatter.COLORS['BOLD']}{ConsoleFormatter.COLORS['BLUE']}=== {message} ==={ConsoleFormatter.COLORS['RESET']}\n"
    
    @staticmethod
    def print_table(headers: List[str], rows: List[List[str]], title: Optional[str] = None) -> None:
        """Imprime una tabla formateada."""
        if title:
            print(ConsoleFormatter.header(title))
        
        try:
            from tabulate import tabulate
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        except ImportError:
            # Fallback sin tabulate
            print(" | ".join(headers))
            print("-" * 60)
            for row in rows:
                print(" | ".join(row))


class ConfigValidator:
    """Valida configuraciones del sistema."""
    
    @staticmethod
    def validate_ssid(ssid: str) -> tuple[bool, str]:
        """
        Valida un SSID.
        
        Returns:
            tuple: (is_valid, message)
        """
        if not ssid:
            return False, "SSID no puede estar vacío"
        if len(ssid) > 32:
            return False, "SSID no puede exceder 32 caracteres"
        if len(ssid) < 1:
            return False, "SSID debe tener al menos 1 carácter"
        return True, "SSID válido"
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """
        Valida una contraseña.
        
        Returns:
            tuple: (is_valid, message)
        """
        if not password:
            return False, "Contraseña no puede estar vacía"
        if len(password) < 8:
            return False, "Contraseña debe tener mínimo 8 caracteres"
        if len(password) > 63:
            return False, "Contraseña no puede exceder 63 caracteres"
        return True, "Contraseña válida"
    
    @staticmethod
    def validate_mac_address(mac: str) -> tuple[bool, str]:
        """
        Valida una dirección MAC.
        
        Returns:
            tuple: (is_valid, message)
        """
        import re
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if re.match(mac_pattern, mac):
            return True, "MAC válida"
        return False, "Formato de MAC inválido"


class FileHandler:
    """Maneja operaciones de archivo."""
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """
        Crea un directorio si no existe.
        
        Returns:
            bool: True si se creó o ya existe, False en caso de error.
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creando directorio: {e}")
            return False
    
    @staticmethod
    def save_json(data: Dict[str, Any], filepath: str) -> bool:
        """
        Guarda datos en formato JSON.
        
        Returns:
            bool: True si se guardó, False en caso de error.
        """
        import json
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando JSON: {e}")
            return False
    
    @staticmethod
    def load_json(filepath: str) -> Optional[Dict[str, Any]]:
        """
        Carga datos desde un archivo JSON.
        
        Returns:
            dict: Datos cargados o None en caso de error.
        """
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando JSON: {e}")
            return None


class SystemInfo:
    """Proporciona información del sistema."""
    
    @staticmethod
    def get_python_version() -> str:
        """Obtiene la versión de Python."""
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    @staticmethod
    def get_platform() -> str:
        """Obtiene la plataforma del sistema."""
        import platform
        return platform.platform()
    
    @staticmethod
    def get_timestamp() -> str:
        """Obtiene el timestamp actual formateado."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def get_ip_config() -> Dict[str, Any]:
        """
        Obtiene información de configuración IP.
        
        Returns:
            dict: Información de IP del sistema.
        """
        import socket
        import subprocess
        
        try:
            hostname = socket.gethostname()
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                "hostname": hostname,
                "ipconfig_output": result.stdout[:500]  # Primeros 500 caracteres
            }
        except Exception as e:
            return {"error": str(e)}


class Logger:
    """Utilidades de logging."""
    
    @staticmethod
    def log_to_file(message: str, filepath: str = "hotspot.log") -> bool:
        """
        Registra un mensaje en un archivo.
        
        Returns:
            bool: True si se registró correctamente.
        """
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
            return True
        except Exception as e:
            print(f"Error al registrar: {e}")
            return False
    
    @staticmethod
    def get_log_file(filepath: str = "hotspot.log", lines: int = 50) -> str:
        """
        Obtiene las últimas líneas del archivo de log.
        
        Returns:
            str: Contenido del log.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Error leyendo log: {e}"
