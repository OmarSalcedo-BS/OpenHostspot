"""Punto de acceso Wi-Fi Direct usando la API de Windows."""

import asyncio
import logging
import threading
from typing import Any, Optional

import comtypes
import winrt.windows.devices.enumeration
import winrt.windows.networking
import winrt.windows.security.credentials
from winrt.windows.devices.wifidirect import (
    WiFiDirectAdvertisementPublisher,
    WiFiDirectAdvertisementPublisherStatus,
    WiFiDirectConnectionListener,
    WiFiDirectConnectionStatus,
    WiFiDirectDevice,
)


logger = logging.getLogger(__name__)


class WiFiDirectAccessPoint:
    def __init__(self) -> None:
        self._publisher: Optional[Any] = None
        self._listener: Optional[Any] = None
        self._publisher_token: Optional[Any] = None
        self._listener_token: Optional[Any] = None
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._devices: dict[str, Any] = {}
        self._device_details: dict[str, dict[str, str]] = {}
        self._device_markers: dict[str, object] = {}
        self._device_events: list[dict[str, str]] = []
        self._stopping = False
        self.status = "stopped"
        self.error: Optional[str] = None

    def _status_changed(self, sender: Any, args: Any) -> None:
        with self._lock:
            if args.status == WiFiDirectAdvertisementPublisherStatus.STARTED:
                self.status = "started"
            elif args.status == WiFiDirectAdvertisementPublisherStatus.ABORTED:
                self.status = "aborted"
                self.error = f"Wi-Fi Direct cancelado: {args.error.name}"
                logger.error("%s", self.error)
            elif args.status == WiFiDirectAdvertisementPublisherStatus.STOPPED:
                self.status = "stopped"
            self._event.set()

    def _connection_requested(self, sender: Any, args: Any) -> None:
        request = None
        try:
            request = args.get_connection_request()
            device_id = request.device_information.id
            try:
                device_name = request.device_information.name or "Dispositivo Wi-Fi"
            except Exception:
                logger.exception("No se pudo obtener el nombre del cliente Wi-Fi Direct")
                device_name = "Dispositivo Wi-Fi"
        except Exception as error:
            logger.exception("No se pudo leer la solicitud Wi-Fi Direct")
            with self._lock:
                if not self._stopping:
                    self._device_events.append({"kind": "error", "name": "Dispositivo Wi-Fi", "error": str(error)})
            if request is not None:
                try:
                    request.close()
                except Exception:
                    logger.exception("No se pudo cerrar la solicitud Wi-Fi Direct")
            return

        def accept() -> None:
            initialized = False
            device = None
            retained = False
            try:
                comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
                initialized = True
                async def connect() -> Any:
                    return await asyncio.wait_for(WiFiDirectDevice.from_id_async(device_id), timeout=15)

                device = asyncio.run(connect())
                if device is None:
                    raise RuntimeError("Windows no pudo aceptar la conexión Wi-Fi Direct")
                remote = ""
                try:
                    endpoints = device.get_connection_endpoint_pairs()
                    if endpoints and endpoints[0].remote_host_name:
                        remote = endpoints[0].remote_host_name.display_name
                except Exception:
                    logger.exception("No se pudo consultar la dirección del cliente Wi-Fi Direct")
                actual_id = device.device_id
                marker = object()
                device.add_connection_status_changed(
                    lambda sender, event: self._connection_changed(sender, event, marker)
                )
                with self._lock:
                    accepting = (not self._stopping and
                                 device.connection_status == WiFiDirectConnectionStatus.CONNECTED)
                    old_device = self._devices.get(actual_id) if accepting else None
                    if accepting:
                        details = {"id": actual_id, "name": device_name, "ip": remote}
                        self._devices[actual_id] = device
                        self._device_details[actual_id] = details
                        self._device_markers[actual_id] = marker
                        retained = True
                        if old_device is None:
                            self._device_events.append({"kind": "connected", **details})
                if not accepting:
                    device.close()
                    return
                if old_device:
                    old_device.close()
            except Exception as error:
                logger.exception("No se pudo aceptar la conexión Wi-Fi Direct")
                with self._lock:
                    if not self._stopping:
                        self._device_events.append({"kind": "error", "name": device_name,
                                                    "error": str(error) or type(error).__name__})
                if device is not None and not retained:
                    try:
                        device.close()
                    except Exception:
                        logger.exception("No se pudo liberar el cliente Wi-Fi Direct")
            finally:
                try:
                    request.close()
                except Exception:
                    logger.exception("No se pudo cerrar la solicitud Wi-Fi Direct")
                finally:
                    if initialized:
                        comtypes.CoUninitialize()

        threading.Thread(target=accept, daemon=True).start()

    def _connection_changed(self, device: Any, args: Any, marker: object) -> None:
        if device.connection_status == WiFiDirectConnectionStatus.DISCONNECTED:
            with self._lock:
                if self._device_markers.get(device.device_id) is not marker:
                    return
                stored = self._devices.pop(device.device_id, None)
                details = self._device_details.pop(device.device_id)
                self._device_markers.pop(device.device_id)
                if not self._stopping:
                    self._device_events.append({"kind": "disconnected", **details})
            if stored:
                stored.close()

    def connected_devices(self) -> list[dict[str, str]]:
        with self._lock:
            return [details.copy() for details in self._device_details.values()]

    def take_device_events(self) -> list[dict[str, str]]:
        with self._lock:
            events = self._device_events
            self._device_events = []
            return events

    def start(self, ssid: str, password: str, timeout: float = 15) -> dict[str, Any]:
        if self._publisher is not None:
            return {"success": False, "error": "Ya hay una sesión Wi-Fi Direct en curso."}
        self._stopping = False
        self.error = None
        self._event.clear()
        try:
            self._publisher = WiFiDirectAdvertisementPublisher()
            advertisement = self._publisher.advertisement
            advertisement.is_autonomous_group_owner_enabled = True
            legacy = advertisement.legacy_settings
            legacy.is_enabled = True
            legacy.ssid = ssid
            legacy.passphrase.password = password
            self._listener = WiFiDirectConnectionListener()
            self._listener_token = self._listener.add_connection_requested(self._connection_requested)
            self._publisher_token = self._publisher.add_status_changed(self._status_changed)
            self._publisher.start()
            if not self._event.wait(timeout):
                raise TimeoutError("Windows no confirmó el inicio de Wi-Fi Direct.")
            if self.status != "started":
                raise RuntimeError(self.error or f"Wi-Fi Direct no se inició: {self.status}")
            return {"success": True}
        except Exception as error:
            logger.exception("No se pudo iniciar Wi-Fi Direct")
            cleanup = self.stop()
            detail = str(error)
            if not cleanup["success"]:
                detail += f". Error al detener Wi-Fi Direct: {cleanup['error']}"
            return {"success": False, "error": detail}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stopping = True
            devices = list(self._devices.values())
            self._devices.clear()
            self._device_details.clear()
            self._device_markers.clear()
            self._device_events.clear()
        errors = []
        if self._listener is not None and self._listener_token is not None:
            try:
                self._listener.remove_connection_requested(self._listener_token)
                self._listener_token = None
                self._listener = None
            except Exception as error:
                errors.append(f"listener: {error}")
        for device in devices:
            try:
                device.close()
            except Exception as error:
                errors.append(f"cliente: {error}")
        if self._publisher is not None:
            try:
                was_running = self.status == "started"
                self._event.clear()
                self._publisher.stop()
                if was_running and not self._event.wait(5):
                    raise TimeoutError("Windows no confirmó la detención de Wi-Fi Direct.")
                if was_running and self.status not in ("stopped", "aborted"):
                    raise RuntimeError(f"Estado inesperado al detener Wi-Fi Direct: {self.status}")
                if self._publisher_token is not None:
                    self._publisher.remove_status_changed(self._publisher_token)
                self._publisher_token = None
                self._publisher = None
            except Exception as error:
                errors.append(f"publicación: {error}")
        if errors:
            logger.error("Errores al detener Wi-Fi Direct: %s", "; ".join(errors))
            return {"success": False, "error": "; ".join(errors)}
        self.status = "stopped"
        return {"success": True}
