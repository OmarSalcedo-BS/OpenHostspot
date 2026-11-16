import comtypes.client
import ctypes
import subprocess
from typing import Dict, List, Any, Optional
from enum import Enum


class ConnectionType(Enum):
    """Tipos de conexión de red."""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    VPN = "vpn"
    UNKNOWN = "unknown"


class ICSBridge:
    """
    Gestiona el Puente de Conexión a Internet (ICS - Internet Connection Sharing)
    en Windows utilizando los objetos COM de red de Microsoft (HNetCfg.HNetShare).
    """

    def __init__(self) -> None:
        self.net_share: Optional[Any] = None
        self._initialize_com()

    def _initialize_com(self) -> None:
        """Inicializa el objeto COM para la compartición de red."""
        try:
            self.net_share = comtypes.client.CreateObject("HNetCfg.HNetShare")
        except Exception as e:
            print(f"Advertencia: No se pudo inicializar COM para ICS: {e}")
            self.net_share = None

    @staticmethod
    def is_admin() -> bool:
        """Verifica si el proceso actual cuenta con privilegios de Administrador."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    def list_connections(self) -> List[Dict[str, Any]]:
        """
        Lista todas las conexiones de red disponibles en el sistema.
        
        Returns:
            list: Lista de diccionarios con información de conexiones.
        """
        if not self.net_share:
            return []
        
        try:
            connections = []
            for conn in self.net_share.EnumEveryConnection:
                try:
                    props = self.net_share.NetConnectionProps(conn)
                    connections.append({
                        "name": props.Name,
                        "type": self._get_connection_type(props.MediaType),
                        "status": "connected" if props.Status == 2 else "disconnected"
                    })
                except Exception as e:
                    print(f"Error obteniendo propiedades de conexión: {e}")
                    continue
            return connections
        except Exception as e:
            print(f"Error listando conexiones: {e}")
            return []

    @staticmethod
    def _get_connection_type(media_type: int) -> str:
        """
        Determina el tipo de conexión basado en el tipo de medio.
        
        Args:
            media_type: Código del tipo de medio.
            
        Returns:
            str: Tipo de conexión identificado.
        """
        media_types = {
            0: "ethernet",
            1: "token_ring",
            2: "fddi",
            3: "bda",
            4: "arcnet",
            5: "atm",
            6: "wireless",
            7: "irda",
            8: "tunnel",
            9: "ieee1394"
        }
        return media_types.get(media_type, "unknown")

    def enable_ics(self, public_connection_name: str, private_connection_name: str,
                   private_connection_guid: Optional[str] = None) -> Dict[str, Any]:
        """
        Habilita la Compartición de Conexión a Internet (ICS) desde una interfaz pública 
        (ej. Ethernet con internet) hacia una interfaz privada (ej. el Adaptador Virtual del Hotspot).
        
        Args:
            public_connection_name: Nombre del adaptador con internet (ej. "Ethernet").
            private_connection_name: Nombre del adaptador virtual del hotspot.
            private_connection_guid: GUID esperado del adaptador virtual, si está disponible.
            
        Returns:
            dict: Estado del resultado de la operación.
        """
        if not self.is_admin():
            return {"success": False, "error": "Se requieren privilegios de Administrador para configurar el ICS."}

        if not self.net_share:
            return {"success": False, "error": "COM no inicializado. Verifica que comtypes esté instalado."}

        try:
            if not public_connection_name or not private_connection_name:
                return {"success": False, "error": "Selecciona las interfaces pública y privada."}
            if public_connection_name == private_connection_name:
                return {"success": False, "error": "Las interfaces pública y privada deben ser diferentes."}
            connections = self.net_share.EnumEveryConnection
            public_conn_mapped = None
            private_conn_mapped = None

            # Buscar las conexiones por su nombre en el sistema operativo
            for conn in connections:
                props = self.net_share.NetConnectionProps(conn)
                name = props.Name
                config = self.net_share.INetSharingConfigurationForINetConnection(conn)
                if config.SharingEnabled:
                    return {"success": False, "error": (
                        f"ICS ya está activo en '{name}'. Desactívalo manualmente antes de continuar."
                    )}
                
                if name == public_connection_name:
                    public_conn_mapped = conn
                elif name == private_connection_name:
                    if (private_connection_guid is not None and
                            str(props.Guid).strip("{}").casefold() !=
                            private_connection_guid.strip("{}").casefold()):
                        return {"success": False, "error": (
                            "El GUID del adaptador privado cambió; no se modificó ICS."
                        )}
                    private_conn_mapped = conn

            if not public_conn_mapped:
                return {"success": False, "error": f"No se encontró la conexión pública: '{public_connection_name}'"}
            
            if not private_conn_mapped:
                return {"success": False, "error": f"No se encontró la conexión privada: '{private_connection_name}'"}

            # Obtener la configuración de compartición para ambas interfaces
            pub_config = self.net_share.INetSharingConfigurationForINetConnection(public_conn_mapped)
            priv_config = self.net_share.INetSharingConfigurationForINetConnection(private_conn_mapped)

            # Habilitar ICS (0 = Habilitar como público, 1 = Habilitar como privado)
            pub_config.EnableSharing(0)
            try:
                priv_config.EnableSharing(1)
            except Exception as e:
                try:
                    pub_config.DisableSharing()
                except Exception as rollback_error:
                    return {"success": False, "error": (
                        f"Error al activar ICS: {e}. No se pudo revertir la interfaz pública: {rollback_error}"
                    )}
                return {"success": False, "error": f"Error al activar ICS: {e}. Se revirtió la interfaz pública."}

            return {
                "success": True, 
                "message": f"ICS habilitado exitosamente de '{public_connection_name}' a '{private_connection_name}'."
            }

        except Exception as e:
            return {"success": False, "error": f"Error al configurar ICS mediante COM: {str(e)}"}

    def disable_ics(self, private_connection_name: str) -> Dict[str, Any]:
        """
        Deshabilita la Compartición de Conexión a Internet en una interfaz dada.
        
        Args:
            private_connection_name: Nombre del adaptador a descompartir.
            
        Returns:
            dict: Estado del resultado.
        """
        if not self.net_share:
            return {"success": False, "error": "COM no inicializado."}
        
        try:
            connections = self.net_share.EnumEveryConnection

            for conn in connections:
                props = self.net_share.NetConnectionProps(conn)
                if props.Name == private_connection_name:
                    config = self.net_share.INetSharingConfigurationForINetConnection(conn)
                    config.DisableSharing()
                    return {"success": True, "message": f"ICS desactivado para '{private_connection_name}'."}

            return {"success": False, "error": f"No se encontró la conexión: '{private_connection_name}'"}

        except Exception as e:
            return {"success": False, "error": f"Error al desactivar ICS: {str(e)}"}

    def get_ics_status(self, connection_name: str) -> Dict[str, Any]:
        """
        Obtiene el estado del ICS para una conexión específica.
        
        Args:
            connection_name: Nombre de la conexión.
            
        Returns:
            dict: Estado del ICS en esa conexión.
        """
        if not self.net_share:
            return {"success": False, "status": "unknown"}
        
        try:
            for conn in self.net_share.EnumEveryConnection:
                props = self.net_share.NetConnectionProps(conn)
                if props.Name == connection_name:
                    config = self.net_share.INetSharingConfigurationForINetConnection(conn)
                    return {
                        "success": True,
                        "connection": connection_name,
                        "sharing_enabled": config.SharingEnabled
                    }
            return {"success": False, "error": f"Conexión no encontrada: {connection_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def reset_ics() -> Dict[str, Any]:
        """
        Reinicia completamente el servicio ICS del sistema.
        
        Returns:
            dict: Estado de la operación.
        """
        if not ICSBridge.is_admin():
            return {"success": False, "error": "Se requieren privilegios de Administrador."}
        
        try:
            subprocess.run(
                ["netsh", "int", "ip", "reset", "resetlog.txt"],
                capture_output=True, check=True
            )
            return {"success": True, "message": "Servicio ICS reiniciado."}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": str(e)}

    def detect_internet_interface(self) -> Optional[str]:
        """
        Detecta automáticamente el adaptador con conexión a internet.
        
        Returns:
            str: Nombre del adaptador con internet o None si no se detecta.
        """
        connections = self.list_connections()
        
        # Preferencia: Ethernet > Wireless > otros
        for conn in connections:
            if conn["type"] == "ethernet" and conn["status"] == "connected":
                return conn["name"]
        
        for conn in connections:
            if conn["type"] == "wireless" and conn["status"] == "connected":
                return conn["name"]
        
        for conn in connections:
            if conn["status"] == "connected":
                return conn["name"]
        
        return None

    def find_virtual_adapter(self) -> Optional[str]:
        """
        Busca el adaptador virtual del hotspot.
        
        Returns:
            str: Nombre del adaptador virtual o None.
        """
        connections = self.list_connections()
        
        # Patrones comunes para adaptadores virtuales
        virtual_patterns = ["virtual", "hosted", "microsoft", "local area connection*"]
        
        for conn in connections:
            name_lower = conn["name"].lower()
            for pattern in virtual_patterns:
                if pattern in name_lower:
                    return conn["name"]
        
        return None

    def get_ics_configuration_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre la configuración ICS actual.
        
        Returns:
            dict: Información de configuración ICS.
        """
        if not self.net_share:
            return {"success": False, "message": "COM no inicializado"}
        
        try:
            config_info = {
                "public_connections": [],
                "private_connections": []
            }
            
            for conn in self.net_share.EnumEveryConnection:
                props = self.net_share.NetConnectionProps(conn)
                config = self.net_share.INetSharingConfigurationForINetConnection(conn)
                
                conn_info = {
                    "name": props.Name,
                    "type": self._get_connection_type(props.MediaType),
                    "sharing_enabled": config.SharingEnabled
                }
                
                # Determinar si es pública o privada (simplificado)
                if config.SharingEnabled:
                    config_info["private_connections"].append(conn_info)
            
            return {"success": True, "data": config_info}
        except Exception as e:
            return {"success": False, "error": str(e)}