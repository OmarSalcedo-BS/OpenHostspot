"""Vista de dispositivos y tráfico del punto de acceso."""

from typing import Any, Callable

import customtkinter as ctk

from .theme import ACCENT, MUTED, card, label


class DevicesPage(ctk.CTkFrame):
    def __init__(self, parent: Any, speed_test: Callable[[], None]) -> None:
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        label(self, "DISPOSITIVOS Y VELOCIDAD", size=10, color=ACCENT, bold=True).grid(row=0, column=0, sticky="w")
        label(self, "Actividad del hotspot", size=25, bold=True).grid(row=1, column=0, sticky="w", pady=(2, 14))
        traffic = card(self)
        traffic.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        traffic.grid_columnconfigure(0, weight=1)
        label(traffic, "Tráfico actual del adaptador", size=16, bold=True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        self.traffic_label = label(traffic, "Sin datos: inicia el hotspot con ICS.", size=13, color=MUTED, anchor="w")
        self.traffic_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.speed_label = label(traffic, "Prueba de velocidad: sin ejecutar.", size=12, color=MUTED, anchor="w")
        self.speed_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        self.speed_button = ctk.CTkButton(
            traffic, text="Medir internet", fg_color="#24384a", hover_color="#31516a", command=speed_test,
        )
        self.speed_button.grid(row=0, column=1, rowspan=2, padx=18, pady=16)
        label(traffic, "La prueba usa Cloudflare, comparte tu IP y consume hasta 13 MiB de datos.", size=11,
              color=MUTED, anchor="w").grid(row=3, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 14))
        clients = card(self)
        clients.grid(row=3, column=0, sticky="nsew")
        clients.grid_columnconfigure(0, weight=1)
        clients.grid_rowconfigure(2, weight=1)
        label(clients, "Dispositivos", size=16, bold=True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        label(clients, "Conexiones informadas por Wi-Fi Direct y vecinos IPv4 observados; "
              "Windows puede no informar de todos los dispositivos.", size=11,
              color=MUTED, anchor="w", wraplength=700, justify="left").grid(
                  row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.list_frame = ctk.CTkScrollableFrame(clients, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        label(self.list_frame, "Actividad reciente", size=13, bold=True).pack(anchor="w", padx=6, pady=(4, 4))
        self.events_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.events_frame.pack(fill="x", padx=6)
        self._events: list[str] = []
        label(self.list_frame, "Conexiones confirmadas", size=13, bold=True).pack(anchor="w", padx=6, pady=(4, 4))
        self.connected_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.connected_frame.pack(fill="x", padx=6)
        label(self.list_frame, "Vecinos IPv4 observados (no confirman conexión)", size=13,
              bold=True).pack(anchor="w", padx=6, pady=(14, 4))
        self.clients_status = label(self.list_frame, "Sin datos: inicia el hotspot.", size=11,
                                    color=MUTED, anchor="w", wraplength=700, justify="left")
        self.clients_status.pack(fill="x", padx=6, pady=(0, 6))
        self.neighbors_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.neighbors_frame.pack(fill="x", padx=6)
        self._device_rows: tuple[tuple[str, str, str], ...] | None = None
        self._neighbor_rows: tuple[tuple[str, str, str], ...] | None = None
        label(clients, "Bloqueo de internet y lista blanca: no disponibles con el motor actual.",
              size=11, color="#ffd18a", anchor="w", wraplength=700, justify="left").grid(
                  row=3, column=0, sticky="ew", padx=18, pady=(0, 16))

    def add_event(self, message: str) -> None:
        self._events.append(message)
        self._events = self._events[-20:]
        for child in self.events_frame.winfo_children():
            child.destroy()
        for event in reversed(self._events):
            label(self.events_frame, event, size=11, color="#8bddfb", anchor="w").pack(fill="x", pady=2)

    def clear_events(self) -> None:
        self._events.clear()
        for child in self.events_frame.winfo_children():
            child.destroy()

    def show_neighbors(self, neighbors: list[dict[str, str]]) -> None:
        rows = tuple((neighbor["ip"], neighbor["mac"], neighbor["state"]) for neighbor in neighbors)
        if rows == self._neighbor_rows:
            return
        self._neighbor_rows = rows
        for child in self.neighbors_frame.winfo_children():
            child.destroy()
        if not rows:
            label(self.neighbors_frame, "No hay vecinos observados en este momento.", color=MUTED).pack(anchor="w")
            return
        for ip, mac, state in rows:
            label(self.neighbors_frame, f"{ip}   ·   {mac}   ·   {state}", anchor="w").pack(fill="x", pady=4)

    def show_devices(self, devices: list[dict[str, str]]) -> None:
        rows = tuple((device["id"], device["name"], device["ip"]) for device in devices)
        if rows == self._device_rows:
            return
        self._device_rows = rows
        for child in self.connected_frame.winfo_children():
            child.destroy()
        if not rows:
            label(self.connected_frame, "Aún no hay conexiones confirmadas.", color=MUTED).pack(anchor="w")
        for _, name, ip in rows:
            label(self.connected_frame, f"{name}  ·  {ip or 'IP no disponible'}", anchor="w").pack(fill="x", pady=4)
