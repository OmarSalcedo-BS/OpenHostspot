"""Vistas integradas de configuración, ajustes y dispositivos."""

from typing import Any, Callable

import customtkinter as ctk

from .theme import ACCENT, MUTED, card, label


class HotspotPage(ctk.CTkFrame):
    def __init__(self, parent: Any, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=3, uniform="content")
        self.grid_columnconfigure(1, weight=2, uniform="content")
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 22))
        header.grid_columnconfigure(0, weight=1)
        label(header, "PUNTO DE ACCESO", size=10, color=ACCENT, bold=True).grid(row=0, column=0, sticky="w")
        self.status_label = label(header, "Listo para configurar", size=25, bold=True)
        self.status_label.grid(row=1, column=0, sticky="w")
        self.start_button = ctk.CTkButton(
            header, text="Iniciar punto de acceso", width=190, height=40,
            fg_color=ACCENT, hover_color="#078abc", text_color="#06121b",
            font=ctk.CTkFont(size=12, weight="bold"), command=app._start,
        )
        self.start_button.grid(row=0, column=1, rowspan=2, padx=(14, 8))
        self.stop_button = ctk.CTkButton(
            header, text="Detener", width=105, height=40, fg_color="transparent",
            hover_color="#25313e", border_width=1, border_color="#425162", command=app._stop,
        )
        self.stop_button.grid(row=0, column=2, rowspan=2)
        self.banner = label(
            self, "Se modificará la configuración de red de Windows.", size=12,
            color="#9bdaf4", anchor="w", fg_color="#112c3b", corner_radius=8, height=38,
        )
        self.banner.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14), ipady=2, ipadx=12)

        settings = card(self)
        settings.grid(row=2, column=0, sticky="nsew", padx=(0, 14))
        settings.grid_columnconfigure((0, 1), weight=1)
        label(settings, "Configuración del hotspot", size=16, bold=True).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 2))
        label(settings, "Define la red y el origen de internet.", size=12, color=MUTED).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=20)
        label(settings, "MODO", size=10, color=MUTED, bold=True).grid(
            row=2, column=0, sticky="w", padx=20, pady=(22, 6))
        label(settings, "Wi-Fi  •  Wi-Fi Direct", size=12, color="#8bddfb",
              fg_color="#123b50", corner_radius=8, height=42).grid(
                  row=3, column=0, columnspan=2, sticky="ew", padx=20)
        label(settings, "Internet a compartir", size=12, bold=True).grid(
            row=4, column=0, sticky="w", padx=20, pady=(18, 5))
        self.public_box = ctk.CTkComboBox(
            settings, variable=app.public_interface, values=[], height=37,
            border_color="#3c4b5c", fg_color="#0c121a", button_color="#253543",
        )
        self.public_box.grid(row=5, column=0, columnspan=2, sticky="ew", padx=20)
        label(settings, "El adaptador del hotspot se detecta automáticamente.", size=10,
              color=MUTED, anchor="w").grid(row=6, column=0, columnspan=2, sticky="w", padx=20, pady=(6, 0))
        label(settings, "Nombre de la red", size=12, bold=True).grid(
            row=7, column=0, sticky="w", padx=(20, 8), pady=(16, 5))
        label(settings, "Contraseña", size=12, bold=True).grid(
            row=7, column=1, sticky="w", padx=(8, 20), pady=(16, 5))
        self.ssid_entry = ctk.CTkEntry(
            settings, textvariable=app.ssid, height=37, border_color="#3c4b5c", fg_color="#0c121a")
        self.ssid_entry.grid(row=8, column=0, sticky="ew", padx=(20, 8))
        self.password_entry = ctk.CTkEntry(
            settings, textvariable=app.password, show="*", height=37,
            border_color="#3c4b5c", fg_color="#0c121a")
        self.password_entry.grid(row=8, column=1, sticky="ew", padx=(8, 20))
        label(settings, "Hasta 32 caracteres", size=10, color=MUTED).grid(
            row=9, column=0, sticky="w", padx=20, pady=(4, 0))
        ctk.CTkCheckBox(
            settings, text="Mostrar contraseña", width=140, variable=app.show_password,
            checkbox_width=15, checkbox_height=15, font=ctk.CTkFont(size=10),
            command=app._toggle_password,
        ).grid(row=9, column=1, sticky="w", padx=8, pady=(6, 0))
        self.share_switch = ctk.CTkSwitch(
            settings, text="Compartir internet (ICS)", variable=app.share_internet,
            progress_color=ACCENT, command=app._update_controls,
        )
        self.share_switch.grid(row=10, column=0, columnspan=2, sticky="w", padx=20, pady=(24, 10))
        ctk.CTkButton(settings, text="Ver código QR", height=34, fg_color="#24384a",
                      hover_color="#31516a", command=app._show_qr).grid(
                          row=11, column=0, sticky="w", padx=20, pady=(6, 20))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=2, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        diagnostic = card(right)
        diagnostic.grid(row=0, column=0, sticky="ew")
        diagnostic.grid_columnconfigure(0, weight=1)
        label(diagnostic, "Estado del sistema", size=16, bold=True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 6))
        label(diagnostic, "Compatibilidad de este equipo", size=11, color=MUTED).grid(
            row=1, column=0, sticky="w", padx=18)
        self.driver_label = label(diagnostic, "Wi-Fi Direct GO: comprobando...",
                                  size=12, anchor="w", wraplength=280, justify="left")
        self.driver_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(20, 8))
        self.admin_label = label(diagnostic, "Administrador: comprobando...", size=12, anchor="w")
        self.admin_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 16))
        self.check_button = ctk.CTkButton(
            diagnostic, text="Comprobar de nuevo", height=34,
            fg_color="#24384a", hover_color="#31516a", command=app._check_system,
        )
        self.check_button.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        information = card(right)
        information.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        label(information, "Antes de comenzar", size=15, bold=True).pack(anchor="w", padx=18, pady=(18, 10))
        label(information, "Se requiere administrador y compatibilidad con Wi-Fi Direct GO. "
              "ICS puede modificar la configuración de red de Windows.", size=12, color=MUTED,
              wraplength=270, justify="left").pack(anchor="w", padx=18, pady=(0, 14))
        label(information, "El acceso a internet y el uso de Wi-Fi como origen dependen del "
              "controlador y necesitan verificarse con un dispositivo conectado.", size=12,
              color=MUTED, wraplength=270, justify="left").pack(anchor="w", padx=18, pady=(0, 18))


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent: Any, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        label(self, "AJUSTES", size=10, color=ACCENT, bold=True).pack(anchor="w")
        label(self, "Configuración", size=25, bold=True).pack(anchor="w", pady=(2, 4))
        label(self, "Opciones de esta sesión", size=12, color=MUTED).pack(anchor="w", pady=(0, 20))
        network = card(self)
        network.pack(fill="x", pady=(0, 14))
        label(network, "Red", size=16, bold=True).pack(anchor="w", padx=20, pady=(18, 10))
        self.share_switch = ctk.CTkSwitch(
            network, text="Compartir internet mediante ICS", variable=app.share_internet,
            progress_color=ACCENT, command=app._update_controls,
        )
        self.share_switch.pack(anchor="w", padx=20, pady=(0, 8))
        label(network, "Windows configurará ICS solo si identifica el adaptador de destino.",
              size=12, color=MUTED, wraplength=700, justify="left").pack(anchor="w", padx=20, pady=(0, 18))
        privacy = card(self)
        privacy.pack(fill="x", pady=(0, 14))
        label(privacy, "Privacidad", size=16, bold=True).pack(anchor="w", padx=20, pady=(18, 10))
        self.password_switch = ctk.CTkSwitch(
            privacy, text="Mostrar contraseña en la pantalla principal",
            variable=app.show_password, progress_color=ACCENT, command=app._toggle_password,
        )
        self.password_switch.pack(anchor="w", padx=20, pady=(0, 18))


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
        label(clients, "Vecinos observados", size=16, bold=True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        self.clients_status = label(clients, "Sin datos: inicia el hotspot con ICS.", size=11,
                                    color=MUTED, anchor="w", wraplength=700, justify="left")
        self.clients_status.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.list_frame = ctk.CTkScrollableFrame(clients, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        label(clients, "Bloqueo de internet y lista blanca: no disponibles con el motor actual.",
              size=11, color="#ffd18a", anchor="w", wraplength=700, justify="left").grid(
                  row=3, column=0, sticky="ew", padx=18, pady=(0, 16))

    def show_neighbors(self, neighbors: list[dict[str, str]]) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not neighbors:
            label(self.list_frame, "No hay vecinos observados en este momento.", color=MUTED).pack(anchor="w", padx=6)
            return
        for neighbor in neighbors:
            label(self.list_frame,
                  f"{neighbor['ip']}   ·   {neighbor['mac']}   ·   {neighbor['state']}",
                  anchor="w").pack(fill="x", padx=6, pady=4)
