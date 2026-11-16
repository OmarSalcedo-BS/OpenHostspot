"""Estilos compartidos por las vistas."""

from typing import Any

import customtkinter as ctk

BG = "#090c12"
SIDEBAR = "#0e131c"
CARD = "#151c27"
BORDER = "#273342"
MUTED = "#94a3b8"
TEXT = "#eef5ff"
ACCENT = "#15a9df"


def label(parent: Any, text: str, *, size: int = 13, color: str = TEXT,
          bold: bool = False, **kwargs: Any) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent, text=text, text_color=color,
        font=ctk.CTkFont(family="Segoe UI", size=size,
                         weight="bold" if bold else "normal"), **kwargs
    )


def card(parent: Any) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14,
                        border_width=1, border_color=BORDER)
