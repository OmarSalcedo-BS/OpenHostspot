"""Observación pasiva de vecinos y tráfico del adaptador del hotspot."""

import ipaddress
import json
import re
import subprocess
import time
import uuid
from typing import Any

import psutil


class HotspotObserver:
    def __init__(self, adapter_guid: str) -> None:
        self.guid = str(uuid.UUID(adapter_guid.strip("{}")))

    def snapshot(self) -> dict[str, Any]:
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            f"$adapters = @(Get-NetAdapter -IncludeHidden | Where-Object {{ [guid]$_.InterfaceGuid -eq [guid]'{self.guid}' }}); "
            "if ($adapters.Count -ne 1) { throw 'Adaptador del hotspot no encontrado' }; "
            "$adapter = $adapters[0]; "
            "$neighbors = @(Get-NetNeighbor -AddressFamily IPv4 | Where-Object { "
            "$_.InterfaceIndex -eq $adapter.ifIndex -and "
            "@('Reachable','Stale','Delay','Probe') -contains [string]$_.State "
            "} | ForEach-Object { [PSCustomObject]@{ IP = $_.IPAddress; "
            "MAC = $_.LinkLayerAddress; State = [string]$_.State } }); "
            "ConvertTo-Json -InputObject ([PSCustomObject]@{ Name = $adapter.Name; Neighbors = $neighbors }) "
            "-Depth 4 -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            data = json.loads(result.stdout)
            if (not isinstance(data, dict) or not isinstance(data.get("Name"), str)
                    or not isinstance(data.get("Neighbors"), list)):
                raise ValueError("respuesta incompleta de Windows")
            neighbors = []
            for entry in data["Neighbors"]:
                if not isinstance(entry, dict):
                    raise ValueError("vecino de red inválido")
                ip, mac, state = entry.get("IP"), entry.get("MAC"), entry.get("State")
                if not all(isinstance(value, str) for value in (ip, mac, state)):
                    raise ValueError("datos incompletos de un vecino")
                address = ipaddress.ip_address(ip)
                normalized = mac.upper().replace(":", "-")
                if (address.version != 4 or address.is_multicast or address.is_unspecified or address.is_reserved
                        or state not in ("Reachable", "Stale", "Delay", "Probe")
                        or not re.fullmatch(r"[0-9A-F]{2}(?:-[0-9A-F]{2}){5}", normalized)
                        or int(normalized[:2], 16) & 1 or normalized == "00-00-00-00-00-00"):
                    continue
                neighbors.append({"ip": ip, "mac": normalized, "state": state})
            return {"neighbors": neighbors}
        except (OSError, subprocess.SubprocessError, ValueError, TypeError) as error:
            detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
            raise RuntimeError(f"No se pudo observar el adaptador del hotspot: {detail}") from error


class TrafficMonitor:
    def __init__(self, interface_name: str) -> None:
        self.interface_name = interface_name
        self._previous: tuple[float, int, int] | None = None

    def sample(self) -> dict[str, float] | None:
        try:
            counters = psutil.net_io_counters(pernic=True, nowrap=False).get(self.interface_name)
        except OSError as error:
            raise RuntimeError(f"No se pudieron leer los contadores de red: {error}") from error
        if counters is None:
            raise RuntimeError("No hay contadores para el adaptador del hotspot.")
        now = time.monotonic()
        sent, received = counters.bytes_sent, counters.bytes_recv
        previous = self._previous
        self._previous = (now, sent, received)
        if previous is None:
            return None
        previous_time, previous_sent, previous_received = previous
        elapsed = now - previous_time
        if elapsed <= 0 or sent < previous_sent or received < previous_received:
            return None
        return {
            "sent_mbps": (sent - previous_sent) * 8 / elapsed / 1_000_000,
            "received_mbps": (received - previous_received) * 8 / elapsed / 1_000_000,
        }
