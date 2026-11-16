"""Vista principal del punto de acceso."""

from typing import Any

import customtkinter as ctk
from PIL import Image

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
            progress_color=ACCENT, command=app._sharing_changed,
        )
        self.share_switch.grid(row=10, column=0, columnspan=2, sticky="w", padx=20, pady=(24, 10))
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
        active = card(right)
        active.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        active.grid_columnconfigure(1, weight=1)
        label(active, "Red y dispositivos", size=15, bold=True).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))
        self.qr_label = label(active, "El QR aparece\nal iniciar", size=11, color=MUTED, width=144, height=144)
        self.qr_label.grid(row=1, column=0, rowspan=3, padx=(16, 10), pady=(0, 8))
        self.traffic_label = label(active, "Tráfico: sin datos", size=11, color=MUTED,
                                   anchor="w", justify="left", wraplength=150)
        self.traffic_label.grid(row=1, column=1, sticky="ew", padx=(0, 12))
        self.device_count = label(active, "Sin conexiones confirmadas", size=11, color=MUTED,
                                  anchor="w", wraplength=150, justify="left")
        self.device_count.grid(row=2, column=1, sticky="ew", padx=(0, 12))
        self.device_notice = label(active, "", size=11, color="#8bddfb",
                                   anchor="w", wraplength=150, justify="left")
        self.device_notice.grid(row=3, column=1, sticky="ew", padx=(0, 12), pady=(0, 6))
        self.device_list = ctk.CTkScrollableFrame(active, fg_color="transparent", height=68)
        self.device_list.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self._device_rows: tuple[tuple[str, str, str], ...] | None = None
        self.qr_image: ctk.CTkImage | None = None

    def show_qr(self, qr: Any = None, error: str = "") -> None:
        if qr is None:
            self.qr_image = None
            self.qr_label.configure(image=None, text=error or "El QR aparece\nal iniciar")
            return
        image = qr.make_image().convert("RGB").resize((144, 144), Image.Resampling.NEAREST)
        self.qr_image = ctk.CTkImage(light_image=image, dark_image=image, size=(144, 144))
        self.qr_label.configure(image=self.qr_image, text="")

    def show_devices(self, devices: list[dict[str, str]]) -> None:
        rows = tuple((device["id"], device["name"], device["ip"]) for device in devices)
        if rows == self._device_rows:
            return
        self._device_rows = rows
        self.device_count.configure(text=f"{len(rows)} conexión(es) confirmada(s) por Windows")
        for child in self.device_list.winfo_children():
            child.destroy()
        if not rows:
            label(self.device_list, "Aún no hay conexiones confirmadas.", size=11, color=MUTED).pack(anchor="w")
        for _, name, ip in rows:
            label(self.device_list, f"{name}  ·  {ip or 'IP no disponible'}",
                  size=11, anchor="w").pack(fill="x", pady=2)


