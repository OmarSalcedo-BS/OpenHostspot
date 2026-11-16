"""Entrada gráfica sin consola de Windows."""

import logging
import sys
from tkinter import messagebox


if __name__ == "__main__":
    try:
        from gui import main

        raise SystemExit(main())
    except Exception as error:
        logging.exception("No se pudo iniciar OpenHotspot")
        messagebox.showerror("OpenHotspot", f"No se pudo iniciar la aplicación: {error}")
        sys.exit(1)
