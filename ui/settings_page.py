"""Vista integrada de ajustes de red, inicio, energía y visualización."""

from typing import Any

import customtkinter as ctk

from .theme import ACCENT, MUTED, card, label


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent: Any, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        label(self, "AJUSTES", size=10, color=ACCENT, bold=True).pack(anchor="w")
        label(self, "Configuración", size=25, bold=True).pack(anchor="w", pady=(2, 4))
        label(self, "Preferencias de este usuario de Windows", size=12, color=MUTED).pack(anchor="w", pady=(0, 14))
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)

        network = card(content)
        network.pack(fill="x", pady=(0, 12))
        label(network, "Red y seguridad", size=16, bold=True).pack(anchor="w", padx=20, pady=(16, 10))
        self.share_switch = ctk.CTkSwitch(
            network, text="Compartir internet mediante ICS", variable=app.share_internet,
            progress_color=ACCENT, command=app._sharing_changed,
        )
        self.share_switch.pack(anchor="w", padx=20, pady=(0, 10))
        self.password_switch = ctk.CTkSwitch(
            network, text="Mostrar contraseña en la pantalla principal",
            variable=app.show_password, progress_color=ACCENT, command=app._toggle_password,
        )
        self.password_switch.pack(anchor="w", padx=20, pady=(0, 10))
        ctk.CTkButton(network, text="Guardar nombre, contraseña y origen", fg_color="#24384a",
                      hover_color="#31516a", command=app._save_network_settings).pack(
                          anchor="w", padx=20, pady=(0, 8))
        self.save_status = label(network, "", size=11, color=MUTED, wraplength=700, justify="left")
        self.save_status.pack(anchor="w", padx=20)
        label(network, "La contraseña se cifra con la cuenta actual de Windows.",
              size=11, color=MUTED, wraplength=700, justify="left").pack(anchor="w", padx=20, pady=(0, 16))

        startup = card(content)
        startup.pack(fill="x", pady=(0, 12))
        label(startup, "Inicio", size=16, bold=True).pack(anchor="w", padx=20, pady=(16, 10))
        self.startup_switch = ctk.CTkSwitch(
            startup, text="Abrir OpenHotspot al iniciar sesión", variable=app.start_with_windows,
            progress_color=ACCENT, command=app._change_startup,
        )
        self.startup_switch.pack(anchor="w", padx=20, pady=(0, 8))
        self.startup_status = label(startup, "Solo abre la aplicación. Windows puede solicitar administrador.",
                                    size=11, color=MUTED, wraplength=700, justify="left")
        self.startup_status.pack(anchor="w", padx=20, pady=(0, 16))

        power = card(content)
        power.pack(fill="x", pady=(0, 12))
        label(power, "Energía", size=16, bold=True).pack(anchor="w", padx=20, pady=(16, 10))
        self.power_switch = ctk.CTkSwitch(
            power, text="Evitar suspensión automática mientras el hotspot esté activo",
            variable=app.prevent_sleep, progress_color=ACCENT, command=app._power_changed,
        )
        self.power_switch.pack(anchor="w", padx=20, pady=(0, 8))
        self.power_status = label(power, "La pantalla puede apagarse. No impide suspensión manual.",
                                  size=11, color=MUTED, wraplength=700, justify="left")
        self.power_status.pack(anchor="w", padx=20, pady=(0, 16))

        display = card(content)
        display.pack(fill="x", pady=(0, 12))
        label(display, "Visualización", size=16, bold=True).pack(anchor="w", padx=20, pady=(16, 10))
        ctk.CTkSwitch(display, text="Mostrar código QR del hotspot", variable=app.show_qr,
                      progress_color=ACCENT, command=app._visual_changed).pack(anchor="w", padx=20, pady=(0, 10))
        ctk.CTkSwitch(display, text="Mostrar avisos de dispositivos", variable=app.show_device_notices,
                      progress_color=ACCENT, command=app._visual_changed).pack(anchor="w", padx=20, pady=(0, 10))
        row = ctk.CTkFrame(display, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        label(row, "Unidad de tráfico", size=12).pack(side="left", padx=(0, 12))
        ctk.CTkOptionMenu(row, variable=app.speed_unit, values=["Automático", "Mbps"],
                          command=lambda _: app._visual_changed(), fg_color="#24384a",
                          button_color="#31516a").pack(side="left")
