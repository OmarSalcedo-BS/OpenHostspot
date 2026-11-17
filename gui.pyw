"""Entrada gráfica sin consola de Windows."""

import logging
import sys
from tkinter import messagebox


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-bundle"]:
        try:
            from gui import OpenHotspotApp

            app = OpenHotspotApp(auto_check=False)
            app.withdraw()
            app.update()
            app._finish_close()
        except Exception:
            logging.exception("Falló la verificación del ejecutable")
            sys.exit(1)
        sys.exit(0)
    try:
        from gui import main

        raise SystemExit(main())
    except Exception as error:
        logging.exception("No se pudo iniciar OpenHotspot")
        messagebox.showerror("OpenHotspot", f"No se pudo iniciar la aplicación: {error}")
        sys.exit(1)
