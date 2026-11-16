"""Orquestación del anuncio Wi-Fi Direct y la compartición ICS."""

import json
import subprocess
import time
from typing import Any

from .ics_bridge import ICSBridge
from .network_manager import NetworkManager
from .wifi_direct import WiFiDirectAccessPoint


def _direct_adapters() -> dict[str, dict[str, Any]]:
    """Obtiene los adaptadores Wi-Fi Direct con su GUID y estado de Windows."""
    command = (
        "$ErrorActionPreference = 'Stop'; "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$adapters = @(Get-NetAdapter -IncludeHidden | Where-Object { "
        "$_.PnPDeviceID -match '\\\\vwifimp_wfd\\\\' -or "
        "$_.DriverDescription -eq 'Microsoft Wi-Fi Direct Virtual Adapter' "
        "} | ForEach-Object { [PSCustomObject]@{ Name = $_.Name; "
        "Guid = $_.InterfaceGuid.ToString(); Up = ($_.Status -eq 'Up') } }); "
        "ConvertTo-Json -InputObject $adapters -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, encoding="utf-8", errors="replace", timeout=15, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        entries = json.loads(result.stdout)
        if not isinstance(entries, list):
            raise ValueError("respuesta inesperada de Windows")
        adapters: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if (not isinstance(entry, dict) or not isinstance(entry.get("Name"), str)
                    or not isinstance(entry.get("Guid"), str) or not entry["Guid"]
                    or not isinstance(entry.get("Up"), bool)):
                raise ValueError("datos incompletos del adaptador")
            guid = entry["Guid"].strip("{}").casefold()
            if guid in adapters:
                raise ValueError("GUID de adaptador duplicado")
            adapters[guid] = entry
        return adapters
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = error.stderr.strip()
        else:
            detail = str(error)
        raise RuntimeError(f"No se pudieron enumerar los adaptadores Wi-Fi Direct: {detail}") from error


class DirectHotspotController:
    def __init__(self, ssid: str, password: str, public_interface: str) -> None:
        self.ssid = ssid
        self.password = password
        self.public_interface = public_interface
        self.private_interface = ""
        self.private_guid = ""
        self.network = WiFiDirectAccessPoint()
        self.bridge = ICSBridge()
        self._ics_enabled = False

    def start(self, enable_internet_sharing: bool = True) -> dict[str, Any]:
        manager = NetworkManager(self.ssid, self.password)
        validation = manager.validate_credentials()
        if not validation["success"]:
            return {"success": False, "error": "; ".join(validation["errors"])}
        if not manager.is_admin():
            return {"success": False, "error": "Se requieren privilegios de administrador."}
        if enable_internet_sharing and not self.public_interface:
            return {"success": False, "error": "Selecciona la conexión de internet a compartir."}
        try:
            before = _direct_adapters()
        except RuntimeError as error:
            return {"success": False, "error": str(error)}
        if any(adapter["Up"] for adapter in before.values()):
            return {"success": False, "error": (
                "Ya hay un adaptador Wi-Fi Direct activo. Cierra la aplicación o sesión que lo "
                "está usando antes de iniciar OpenHotspot; no se modificó esa sesión."
            )}
        result = self.network.start(self.ssid, self.password)
        if not result["success"]:
            return result
        warning = None
        if enable_internet_sharing:
            try:
                deadline = time.monotonic() + 8
                while True:
                    if self.network.status != "started":
                        raise RuntimeError("La publicación Wi-Fi Direct dejó de estar activa.")
                    adapters = _direct_adapters()
                    active = {guid: adapter for guid, adapter in adapters.items() if adapter["Up"]}
                    if len(active) > 1:
                        raise RuntimeError("Se activaron varios adaptadores Wi-Fi Direct.")
                    if active:
                        guid = next(iter(active))
                        time.sleep(0.5)
                        confirmed = _direct_adapters()
                        active_confirmed = {key: value for key, value in confirmed.items() if value["Up"]}
                        if set(active_confirmed) != {guid}:
                            raise RuntimeError("Cambió la identificación del adaptador Wi-Fi Direct.")
                        if self.network.status != "started":
                            raise RuntimeError("La publicación Wi-Fi Direct dejó de estar activa.")
                        adapter = active_confirmed[guid]
                        self.private_interface = adapter["Name"]
                        self.private_guid = guid
                        ics = self.bridge.enable_ics(
                            self.public_interface, self.private_interface, private_connection_guid=guid
                        )
                        if ics["success"]:
                            self._ics_enabled = True
                        else:
                            warning = ics["error"]
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("No se detectó un adaptador Wi-Fi Direct activo.")
                    time.sleep(0.25)
            except RuntimeError as error:
                warning = f"{error} No se modificó ICS."
        return {"success": True, "internet_shared": self._ics_enabled, "warning": warning}

    def stop(self) -> dict[str, Any]:
        errors = []
        if self._ics_enabled:
            for interface in (self.private_interface, self.public_interface):
                result = self.bridge.disable_ics(interface)
                if not result["success"]:
                    errors.append(result.get("error", f"No se pudo desactivar ICS en {interface}"))
            if not errors:
                self._ics_enabled = False
        network = self.network.stop()
        if not network["success"]:
            return {"success": False, "error": network["error"],
                    "warning": "; ".join(errors) if errors else None}
        return {"success": True, "warning": "; ".join(errors) if errors else None}
