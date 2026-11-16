"""Ajustes por usuario; la contraseña se protege con DPAPI."""

import base64
import binascii
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import pywintypes
import win32crypt


@dataclass
class AppSettings:
    ssid: str = "OpenHotspot"
    password: str = ""
    public_interface: str = ""
    share_internet: bool = True
    prevent_sleep: bool = True
    show_qr: bool = True
    show_device_notices: bool = True
    speed_unit: str = "Automático"


class SettingsError(Exception):
    pass


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        self.path = path if path is not None else local / "OpenHotspot" / "settings.json"

    def load(self) -> AppSettings:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return AppSettings()
        except (OSError, ValueError) as error:
            raise SettingsError(f"No se pudo leer {self.path}: {error}") from error
        if not isinstance(data, dict) or data.get("version") != 1:
            raise SettingsError(f"El archivo {self.path} tiene un formato o versión no compatible.")
        defaults = AppSettings()
        values = {}
        for field in ("ssid", "public_interface", "share_internet", "prevent_sleep",
                      "show_qr", "show_device_notices", "speed_unit"):
            value = data.get(field, getattr(defaults, field))
            if type(value) is not type(getattr(defaults, field)):
                raise SettingsError(f"El ajuste '{field}' no es válido en {self.path}.")
            values[field] = value
        if values["speed_unit"] not in ("Automático", "Mbps"):
            raise SettingsError(f"La unidad de velocidad no es válida en {self.path}.")
        protected = data.get("password_dpapi", "")
        if not isinstance(protected, str):
            raise SettingsError(f"La contraseña protegida no es válida en {self.path}.")
        try:
            password = (win32crypt.CryptUnprotectData(
                base64.b64decode(protected, validate=True), None, None, None, 1
            )[1].decode("utf-8") if protected else "")
        except (binascii.Error, ValueError, UnicodeError, pywintypes.error) as error:
            raise SettingsError(
                f"No se pudo descifrar la contraseña de {self.path} con este usuario de Windows."
            ) from error
        return AppSettings(password=password, **values)

    def save(self, settings: AppSettings) -> None:
        try:
            values = asdict(settings)
            password = values.pop("password")
            protected = (base64.b64encode(win32crypt.CryptProtectData(
                password.encode("utf-8"), "OpenHotspot", None, None, None, 1
            )).decode("ascii") if password else "")
            data = {"version": 1, **values, "password_dpapi": protected}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent,
                    prefix=".openhotspot-", suffix=".tmp", delete=False,
                ) as file:
                    temporary = file.name
                    json.dump(data, file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.path)
                temporary = None
            finally:
                if temporary is not None:
                    Path(temporary).unlink(missing_ok=True)
        except (OSError, ValueError, UnicodeError, pywintypes.error) as error:
            raise SettingsError(f"No se pudieron guardar los ajustes en {self.path}: {error}") from error
