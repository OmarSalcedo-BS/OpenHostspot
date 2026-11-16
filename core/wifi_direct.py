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
        try:
            request = args.get_connection_request()
            device_id = request.device_information.id
        except Exception:
            logger.exception("No se pudo leer la solicitud Wi-Fi Direct")
            return

        def accept() -> None:
            comtypes.CoInitialize()
            try:
                async def connect() -> Any:
                    return await WiFiDirectDevice.from_id_async(device_id)

                device = asyncio.run(connect())
                if device is None:
                    logger.error("Windows no pudo aceptar la conexión Wi-Fi Direct")
                    return
                with self._lock:
                    stopping = self._stopping
                    old_device = None if stopping else self._devices.pop(device_id, None)
                    if not stopping:
                        self._devices[device_id] = device
                if stopping:
                    device.close()
                    return
                if old_device:
                    old_device.close()
                device.add_connection_status_changed(self._connection_changed)
            except Exception:
                logger.exception("No se pudo aceptar la conexión Wi-Fi Direct")
            finally:
                try:
                    request.close()
                finally:
                    comtypes.CoUninitialize()

        threading.Thread(target=accept, daemon=True).start()

    def _connection_changed(self, device: Any, args: Any) -> None:
        if device.connection_status == WiFiDirectConnectionStatus.DISCONNECTED:
            with self._lock:
                stored = self._devices.pop(device.device_id, None)
            if stored:
                stored.close()

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
