#!/usr/bin/env python3
"""Coordinación de la interfaz gráfica de OpenHotspot."""

import ctypes
import logging
import os
import queue
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable, Optional

import comtypes
import customtkinter as ctk
import psutil

from core.direct_controller import DirectHotspotController
from core.hotspot_observer import HotspotObserver, TrafficMonitor
from core.network_manager import NetworkManager
from core.settings_store import AppSettings, SettingsError, SettingsStore
from core.speed_test import measure_speed
from core.windows_integration import SleepInhibitor, StartupManager
from ui.devices_page import DevicesPage
from ui.hotspot_page import HotspotPage
from ui.settings_page import SettingsPage
from ui.theme import ACCENT, BG, MUTED, SIDEBAR, label


logger = logging.getLogger(__name__)


class OpenHotspotApp(ctk.CTk):
    def __init__(self, *, auto_check: bool = True) -> None:
        super().__init__()
        self.title("OpenHotspot")
        self.geometry("1180x740")
        self.minsize(1000, 680)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._executor = ThreadPoolExecutor(max_workers=1, initializer=comtypes.CoInitialize)
        self._telemetry_executor = ThreadPoolExecutor(max_workers=3)
        self._results: queue.Queue = queue.Queue()
        self._telemetry_results: queue.Queue = queue.Queue()
        self._busy = False
        self._closed = False
        self._active = False
        self._controller: Optional[DirectHotspotController] = None
        self._observer: Optional[HotspotObserver] = None
        self._traffic_monitor: Optional[TrafficMonitor] = None
        self._observation_pending = False
        self._traffic_pending = False
        self._next_observation = 0.0
        self._speed_pending = False
        self._abort_reported = False
        self._support: Optional[bool] = None
        self._admin: Optional[bool] = None
        self._current_page = "hotspot"
        self._settings_store = SettingsStore()
        self._settings_available = True
        settings_error = None
        try:
            self._settings = self._settings_store.load()
        except SettingsError as error:
            self._settings = AppSettings()
            self._settings_available = False
            settings_error = str(error)
        self._startup = StartupManager(Path(__file__).with_name("gui.pyw"))
        self._startup_available = True
        try:
            startup_status = self._startup.status()
        except OSError as error:
            startup_status = "error"
            startup_error = str(error)
        else:
            startup_error = ""
        if startup_status in ("error", "conflict"):
            self._startup_available = False
        self._startup_enabled = startup_status == "enabled"
        self._power = SleepInhibitor()
        self._current_qr: Any = None
        self._latest_rates: Optional[dict[str, float]] = None

        self.ssid = ctk.StringVar(value=self._settings.ssid)
        self.password = ctk.StringVar(value=self._settings.password)
        self.public_interface = ctk.StringVar(value=self._settings.public_interface)
        self.share_internet = ctk.BooleanVar(value=self._settings.share_internet)
        self.show_password = ctk.BooleanVar(value=False)
        self.start_with_windows = ctk.BooleanVar(value=self._startup_enabled)
        self.prevent_sleep = ctk.BooleanVar(value=self._settings.prevent_sleep)
        self.show_qr = ctk.BooleanVar(value=self._settings.show_qr)
        self.show_device_notices = ctk.BooleanVar(value=self._settings.show_device_notices)
        self.speed_unit = ctk.StringVar(value=self._settings.speed_unit)

        self._build()
        if not self._startup_available:
            detail = startup_error or "Ya existe una entrada de inicio OpenHotspot diferente; no se modificó."
            self.settings_page.startup_status.configure(text=f"Inicio no disponible: {detail}", text_color="#ffd18a")
        if settings_error:
            logger.error("No se pudieron cargar los ajustes: %s", settings_error)
            messagebox.showerror("Ajustes no disponibles",
                                 f"{settings_error}\n\nNo se sobrescribirá el archivo.", parent=self)
        self._update_controls()
        self.after(100, self._poll_results)
        self.after(1000, self._tick_observer)
        if auto_check:
            self.after(100, self._check_system)

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        label(sidebar, "O", size=22, bold=True, width=42, height=42,
              fg_color=ACCENT, corner_radius=12).pack(anchor="w", padx=22, pady=(30, 8))
        label(sidebar, "OPENHOTSPOT", size=17, bold=True).pack(anchor="w", padx=22)
        label(sidebar, "Tu red, bajo tu control", size=11, color=MUTED).pack(
            anchor="w", padx=22, pady=(0, 35))
        self._nav_buttons = {}
        for key, title in (("hotspot", "Punto de acceso"), ("devices", "Dispositivos"), ("settings", "Ajustes")):
            button = ctk.CTkButton(
                sidebar, text=title, height=42, anchor="w", fg_color="transparent",
                hover_color="#25313e", command=lambda name=key: self._show_page(name),
            )
            button.pack(fill="x", padx=12, pady=3)
            self._nav_buttons[key] = button
        self.activity_notice = label(sidebar, "", size=11, color="#8bddfb",
                                     wraplength=170, justify="left", anchor="w")
        self.activity_notice.pack(fill="x", padx=20, pady=(16, 0))
        label(sidebar, "Open source  •  Windows", size=10, color=MUTED).pack(
            side="bottom", padx=15, pady=25)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=1, sticky="nsew", padx=28, pady=26)
        self.hotspot_page = HotspotPage(container, self)
        self.devices_page = DevicesPage(container, self._run_speed_test)
        self.settings_page = SettingsPage(container, self)
        self._pages = {"hotspot": self.hotspot_page, "devices": self.devices_page,
                       "settings": self.settings_page}
        for page in self._pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.hotspot_page.tkraise()
        self.hotspot_page.show_devices([])
        self.devices_page.show_devices([])
        self.devices_page.show_neighbors([])
        self._highlight_navigation()

    def _highlight_navigation(self) -> None:
        for name, button in self._nav_buttons.items():
            button.configure(fg_color="#123047" if name == self._current_page else "transparent")

    def _show_page(self, name: str) -> None:
        self._pages[name].tkraise()
        self._current_page = name
        self._highlight_navigation()

    def _toggle_password(self) -> None:
        self.hotspot_page.password_entry.configure(show="" if self.show_password.get() else "*")

    def _persist_settings(self, *, include_network: bool = False) -> bool:
        if not self._settings_available:
            messagebox.showerror("Ajustes no disponibles",
                                 "El archivo no se cargó; no se sobrescribirá.", parent=self)
            return False
        updates: dict[str, Any] = {
            "share_internet": self.share_internet.get(),
            "prevent_sleep": self.prevent_sleep.get(),
            "show_qr": self.show_qr.get(),
            "show_device_notices": self.show_device_notices.get(),
            "speed_unit": self.speed_unit.get(),
        }
        if include_network:
            validation = NetworkManager(self.ssid.get(), self.password.get()).validate_credentials()
            if not validation["success"]:
                messagebox.showerror("Configuración inválida", "\n".join(validation["errors"]), parent=self)
                return False
            updates.update(ssid=self.ssid.get(), password=self.password.get(),
                           public_interface=self.public_interface.get().strip())
        settings = replace(self._settings, **updates)
        try:
            self._settings_store.save(settings)
        except SettingsError as error:
            logger.exception("No se pudieron guardar los ajustes")
            messagebox.showerror("Error al guardar ajustes", str(error), parent=self)
            return False
        self._settings = settings
        status = ("Datos de red y preferencias guardados." if include_network else
                  "Preferencias guardadas; guarda los datos de red por separado.")
        self.settings_page.save_status.configure(text=status, text_color="#8bddfb")
        return True

    def _save_network_settings(self) -> None:
        self._persist_settings(include_network=True)

    def _sharing_changed(self) -> None:
        self._update_controls()
        self._persist_settings()

    def _change_startup(self) -> None:
        requested = self.start_with_windows.get()
        try:
            self._startup.set_enabled(requested)
        except (OSError, RuntimeError) as error:
            logger.exception("No se pudo cambiar el inicio automático")
            self.start_with_windows.set(self._startup_enabled)
            self.settings_page.startup_status.configure(text=f"No se pudo cambiar: {error}", text_color="#ffd18a")
            messagebox.showerror("Inicio automático", str(error), parent=self)
            return
        self._startup_enabled = requested
        self.settings_page.startup_status.configure(
            text="Solo abre la aplicación. Windows puede solicitar administrador.", text_color=MUTED)

    def _apply_power(self) -> None:
        desired = self._active and not self._abort_reported and self.prevent_sleep.get()
        try:
            self._power.set_active(desired)
        except (OSError, RuntimeError) as error:
            logger.exception("No se pudo cambiar la solicitud de energía")
            self.settings_page.power_status.configure(text=f"No se pudo aplicar: {error}", text_color="#ffd18a")
            messagebox.showwarning("Energía", f"No se pudo actualizar la prevención de suspensión: {error}",
                                   parent=self)
            return
        text = ("Prevención de suspensión automática activa; la pantalla puede apagarse."
                if desired else "La pantalla puede apagarse. No impide suspensión manual.")
        self.settings_page.power_status.configure(text=text, text_color=MUTED)

    def _power_changed(self) -> None:
        self._apply_power()
        self._persist_settings()

    def _visual_changed(self) -> None:
        if self._active and not self._abort_reported:
            if self.show_qr.get() and self._current_qr is not None:
                self.hotspot_page.show_qr(self._current_qr)
            elif not self.show_qr.get():
                self.hotspot_page.show_qr(error="QR oculto en Ajustes")
        if not self.show_device_notices.get():
            self.hotspot_page.device_notice.configure(text="")
            self.activity_notice.configure(text="")
        if self._latest_rates is not None:
            self._display_traffic(self._latest_rates)
        self._persist_settings()

    def _update_controls(self) -> None:
        editable = not self._busy and not self._active
        page = self.hotspot_page
        page.start_button.configure(state="normal" if editable else "disabled")
        page.stop_button.configure(state="normal" if self._active and not self._busy else "disabled")
        page.check_button.configure(state="normal" if not self._busy else "disabled")
        page.share_switch.configure(state="normal" if editable else "disabled")
        self.settings_page.share_switch.configure(state="normal" if editable else "disabled")
        self.settings_page.power_switch.configure(state="normal" if not self._busy else "disabled")
        self.settings_page.startup_switch.configure(state="normal" if self._startup_available else "disabled")
        for widget in (page.ssid_entry, page.password_entry):
            widget.configure(state="normal" if editable else "disabled")
        page.public_box.configure(state="normal" if editable and self.share_internet.get() else "disabled")
        if not self._active and not self._busy:
            page.banner.configure(text="Modo real: cambiará la red de Windows; requiere administrador.",
                                  text_color="#ffd18a")

    def _submit(self, operation: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        if self._busy:
            return
        self._busy = True
        self._update_controls()
        future = self._executor.submit(operation)
        future.add_done_callback(lambda completed: self._results.put((completed, callback)))

    def _poll_results(self) -> None:
        if (self._active and not self._busy and self._controller is not None
                and self._controller.network.status == "aborted" and not self._abort_reported):
            self._abort_reported = True
            self._apply_power()
            self.hotspot_page.status_label.configure(text="Wi-Fi Direct interrumpido")
            self.hotspot_page.banner.configure(text="La red se interrumpió; detén la sesión para limpiar ICS.",
                                               text_color="#ffd18a")
            self._observer = None
            self._traffic_monitor = None
            self._current_qr = None
            self._latest_rates = None
            self.devices_page.clients_status.configure(text="Wi-Fi Direct se interrumpió; observación detenida.")
            self.devices_page.traffic_label.configure(text="Tráfico no disponible.")
            self.devices_page.show_neighbors([])
            self.devices_page.show_devices([])
            self.hotspot_page.show_devices([])
            self.hotspot_page.traffic_label.configure(text="Tráfico no disponible.")
            self.hotspot_page.show_qr()
            messagebox.showwarning("Wi-Fi Direct", self._controller.network.error or
                                   "La publicación de Wi-Fi Direct se interrumpió.", parent=self)
        try:
            future, callback = self._results.get_nowait()
        except queue.Empty:
            pass
        else:
            self._busy = False
            try:
                callback(future.result())
            except Exception as error:
                logger.exception("Error en operación de la interfaz")
                self.hotspot_page.status_label.configure(text="No se completó la operación")
                messagebox.showerror("OpenHotspot", str(error), parent=self)
            if self._closed:
                return
            self._update_controls()
        while True:
            try:
                kind, owner, future = self._telemetry_results.get_nowait()
            except queue.Empty:
                break
            if kind == "observer":
                self._observation_pending = False
                if owner is self._observer and self._active:
                    self._show_observation(future)
            elif kind == "traffic":
                self._traffic_pending = False
                if owner is self._traffic_monitor and self._active:
                    self._show_traffic(future)
            elif kind == "speed":
                self._speed_pending = False
                self.devices_page.speed_button.configure(state="normal")
                try:
                    result = future.result()
                    self.devices_page.speed_label.configure(
                        text=f"Estimación: ↓ {result['download_mbps']:.2f} Mbps  ·  "
                             f"↑ {result['upload_mbps']:.2f} Mbps (ruta predeterminada del equipo)")
                except Exception as error:
                    logger.exception("Error en la prueba de velocidad")
                    self.devices_page.speed_label.configure(text=f"Prueba fallida: {error}")
        self.after(100, self._poll_results)

    def _tick_observer(self) -> None:
        if self._active and not self._busy and self._controller is not None:
            network = self._controller.network
            devices = network.connected_devices()
            self.hotspot_page.show_devices(devices)
            self.devices_page.show_devices(devices)
            for event in network.take_device_events():
                if event["kind"] == "error":
                    message = f"No se pudo aceptar {event['name']}: {event['error']}"
                else:
                    action = "Se conectó" if event["kind"] == "connected" else "Se desconectó"
                    message = f"{action}: {event['name']}"
                if event["kind"] == "error" or self.show_device_notices.get():
                    self.hotspot_page.device_notice.configure(text=message)
                    self.activity_notice.configure(text=message)
                self.devices_page.add_event(f"{time.strftime('%H:%M:%S')}  ·  {message}")
            if self._traffic_monitor is not None and not self._traffic_pending:
                monitor = self._traffic_monitor
                self._traffic_pending = True
                future = self._telemetry_executor.submit(monitor.sample)
                future.add_done_callback(
                    lambda completed: self._telemetry_results.put(("traffic", monitor, completed)))
            if (self._observer is not None and not self._observation_pending
                    and time.monotonic() >= self._next_observation):
                observer = self._observer
                self._next_observation = time.monotonic() + 5
                self._observation_pending = True
                future = self._telemetry_executor.submit(observer.snapshot)
                future.add_done_callback(
                    lambda completed: self._telemetry_results.put(("observer", observer, completed)))
        self.after(1000, self._tick_observer)

    def _show_observation(self, future: Future) -> None:
        try:
            data = future.result()
        except Exception as error:
            logger.exception("Error al consultar vecinos o tráfico")
            self.devices_page.clients_status.configure(text=f"Observación no disponible: {error}")
            self.devices_page.show_neighbors([])
            return
        self.devices_page.clients_status.configure(
            text="Observaciones IPv4 de Windows; pueden estar desactualizadas o no incluir todos los clientes.")
        self.devices_page.show_neighbors(data["neighbors"])

    def _show_traffic(self, future: Future) -> None:
        try:
            rates = future.result()
        except Exception as error:
            logger.exception("Error al consultar tráfico")
            text = f"Tráfico no disponible: {error}"
            self.devices_page.traffic_label.configure(text=text)
            self.hotspot_page.traffic_label.configure(text=text)
            self._latest_rates = None
            return
        self._latest_rates = rates
        self._display_traffic(rates)

    def _display_traffic(self, rates: Optional[dict[str, float]]) -> None:
        if rates is None:
            text = "Calculando tráfico del adaptador..."
        else:
            def format_rate(mbps: float) -> str:
                if self.speed_unit.get() == "Mbps" or mbps >= 1:
                    return f"{mbps:.2f} Mbps"
                return f"{mbps * 1000:.1f} Kbps"

            text = (f"Enviado: {format_rate(rates['sent_mbps'])}  ·  "
                    f"Recibido: {format_rate(rates['received_mbps'])}")
        self.devices_page.traffic_label.configure(text=text)
        self.hotspot_page.traffic_label.configure(text=text)

    def _run_speed_test(self) -> None:
        if self._speed_pending:
            return
        self._speed_pending = True
        self.devices_page.speed_button.configure(state="disabled")
        self.devices_page.speed_label.configure(text="Midiendo con Cloudflare... usa la ruta predeterminada del equipo.")
        future = self._telemetry_executor.submit(measure_speed)
        future.add_done_callback(lambda completed: self._telemetry_results.put(("speed", None, completed)))

    def _check_system(self) -> None:
        self.hotspot_page.status_label.configure(text="Comprobando el sistema...")

        def check() -> tuple[dict, list[str]]:
            return NetworkManager.get_wifi_direct_support(), sorted(psutil.net_if_stats())

        def complete(result: tuple[dict, list[str]]) -> None:
            capabilities, interfaces = result
            self._admin = bool(NetworkManager.is_admin())
            self._support = capabilities.get("supported")
            support_text = {True: "Compatible", False: "No compatible", None: "No determinado"}[self._support]
            if not capabilities["success"]:
                support_text += f" ({capabilities['error']})"
            self.hotspot_page.driver_label.configure(text=f"Wi-Fi Direct GO: {support_text}")
            self.hotspot_page.admin_label.configure(text=f"Administrador: {'Sí' if self._admin else 'No'}")
            self.hotspot_page.public_box.configure(values=interfaces)
            if not self.public_interface.get():
                self.public_interface.set(next((name for name in interfaces if "ethernet" in name.casefold()), ""))
            self.hotspot_page.status_label.configure(
                text="Punto de acceso iniciado" if self._active else "Listo para configurar")

        self._submit(check, complete)

    def _start(self) -> None:
        manager = NetworkManager(self.ssid.get(), self.password.get())
        validation = manager.validate_credentials()
        if not validation["success"]:
            messagebox.showerror("Configuración inválida", "\n".join(validation["errors"]), parent=self)
            return
        if self._support is False:
            messagebox.showerror("Adaptador no compatible",
                                 "El controlador indica que Wi-Fi Direct GO no está admitido.", parent=self)
            return
        if not manager.is_admin():
            messagebox.showerror("Se requiere administrador",
                                 "Ejecuta la aplicación como administrador.", parent=self)
            return
        public = self.public_interface.get().strip()
        sharing = self.share_internet.get()
        if sharing and not public:
            messagebox.showerror("Conexión necesaria", "Selecciona la conexión de internet a compartir.", parent=self)
            return
        if not self._persist_settings(include_network=True):
            return
        ssid, password = self.ssid.get(), self.password.get()
        self.hotspot_page.status_label.configure(text="Iniciando punto de acceso...")

        def start() -> dict:
            self._controller = DirectHotspotController(ssid, password, public)
            return self._controller.start(enable_internet_sharing=sharing)

        def complete(result: dict) -> None:
            if not result["success"]:
                self.hotspot_page.status_label.configure(text="No se pudo iniciar")
                messagebox.showerror("Error al iniciar", result.get("error", "Error desconocido"), parent=self)
                return
            self._active = True
            self._abort_reported = False
            self._apply_power()
            self.hotspot_page.status_label.configure(text="Punto de acceso iniciado")
            qr = NetworkManager(ssid, password).generate_wifi_qr()
            if qr["success"]:
                self._current_qr = qr["qr"]
                if self.show_qr.get():
                    self.hotspot_page.show_qr(self._current_qr)
                else:
                    self.hotspot_page.show_qr(error="QR oculto en Ajustes")
            else:
                logger.error("No se pudo generar el código QR: %s", qr["error"])
                self.hotspot_page.show_qr(error="No se pudo generar el QR")
            if self._controller is not None and self._controller.private_guid:
                self._observer = HotspotObserver(self._controller.private_guid)
                self._traffic_monitor = TrafficMonitor(self._controller.private_interface)
                self._next_observation = 0
            else:
                self.hotspot_page.traffic_label.configure(text="Tráfico: adaptador no identificado.")
                self.devices_page.traffic_label.configure(text="Tráfico: adaptador no identificado.")
                self.devices_page.clients_status.configure(text="Adaptador no identificado; vecinos no disponibles.")
            warning = result.get("warning")
            if warning:
                banner = "Red iniciada; internet no compartido." if sharing else "Red iniciada; revisa el aviso."
                self.hotspot_page.banner.configure(text=banner, text_color="#ffd18a")
                messagebox.showwarning("Aviso de red", warning, parent=self)
            else:
                text = ("Red iniciada; ICS configurado, conectividad aún no verificada."
                        if result.get("internet_shared") else "Red iniciada sin compartir internet.")
                self.hotspot_page.banner.configure(text=text, text_color="#9bdaf4")

        self._submit(start, complete)

    def _stop(self, *, close_after: bool = False) -> None:
        if not self._active:
            return
        controller = self._controller
        if controller is None:
            messagebox.showerror("Error", "No se encontró el controlador activo.", parent=self)
            return
        self.hotspot_page.status_label.configure(text="Deteniendo punto de acceso...")

        def complete(result: dict) -> None:
            if not result["success"]:
                self.hotspot_page.status_label.configure(text="No se pudo detener")
                error = result.get("error", "Error desconocido")
                if result.get("warning"):
                    error += f"\n\nRevisa ICS: {result['warning']}"
                messagebox.showerror("Error al detener", error, parent=self)
                return
            self._active = False
            self._apply_power()
            self._observer = None
            self._traffic_monitor = None
            self._latest_rates = None
            self._current_qr = None
            self.devices_page.traffic_label.configure(text="Sin datos: inicia el hotspot.")
            self.devices_page.clients_status.configure(text="Sin datos: inicia el hotspot.")
            self.devices_page.show_neighbors([])
            self.devices_page.show_devices([])
            self.devices_page.clear_events()
            self.hotspot_page.show_devices([])
            self.hotspot_page.device_notice.configure(text="")
            self.activity_notice.configure(text="")
            self.hotspot_page.traffic_label.configure(text="Tráfico: sin datos")
            self.hotspot_page.show_qr()
            self.hotspot_page.status_label.configure(text="Listo para configurar")
            if result.get("warning"):
                messagebox.showwarning("Revisa ICS", result["warning"], parent=self)
            if close_after:
                self._finish_close()

        self._submit(controller.stop, complete)

    def _close(self) -> None:
        if self._busy:
            messagebox.showinfo("Operación en curso", "Espera a que termine la operación.", parent=self)
            return
        if self._active:
            if messagebox.askyesno("Cerrar OpenHotspot", "¿Detener el hotspot antes de salir?", parent=self):
                self._stop(close_after=True)
            return
        self._finish_close()

    def _finish_close(self) -> None:
        self._active = False
        self._apply_power()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._telemetry_executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()

    def report_callback_exception(self, exc: type[BaseException], value: BaseException, tb: Any) -> None:
        logger.error("Error en la interfaz", exc_info=(exc, value, tb))
        messagebox.showerror("OpenHotspot", f"Error en la interfaz: {value}", parent=self)


def _configure_logging() -> Path:
    directory = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "OpenHotspot"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "openhotspot.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                        handlers=[handler], force=True)
    return path


def main() -> int:
    if not NetworkManager.is_admin():
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.pyw")
        executable = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.isfile(executable):
            messagebox.showerror("OpenHotspot", f"No se encontró el intérprete gráfico: {executable}")
            return 1
        parameters = subprocess.list2cmdline([script, *sys.argv[1:]])
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, parameters, os.path.dirname(script), 1
        )
        if result <= 32:
            messagebox.showerror(
                "OpenHotspot",
                f"No se pudo iniciar como administrador (código {result}). "
                "Acepta la solicitud de permisos o ejecuta la aplicación desde una consola elevada."
            )
            return 1
        return 0
    try:
        _configure_logging()
    except OSError as error:
        messagebox.showerror("OpenHotspot", f"No se pudo abrir el registro de errores: {error}")
        return 1
    ctk.set_appearance_mode("dark")
    OpenHotspotApp().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
