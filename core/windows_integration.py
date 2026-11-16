"""Inicio de sesión y solicitud temporal de actividad a Windows."""

import ctypes
import os
import subprocess
import sys
import threading
import winreg
from pathlib import Path


class StartupManager:
    KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    NAME = "OpenHotspot"

    def __init__(self, script: Path) -> None:
        self.script = script.resolve()
        self.pythonw = Path(sys.executable).with_name("pythonw.exe")
        self.command = subprocess.list2cmdline([str(self.pythonw), str(self.script)])

    def status(self) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY, 0, winreg.KEY_READ) as key:
                try:
                    value, kind = winreg.QueryValueEx(key, self.NAME)
                except FileNotFoundError:
                    return "disabled"
        except FileNotFoundError:
            return "disabled"
        if kind == winreg.REG_SZ and value == self.command:
            return "enabled"
        return "conflict"

    def set_enabled(self, enabled: bool) -> None:
        if self.status() == "conflict":
            raise RuntimeError("Ya existe una entrada de inicio OpenHotspot diferente; no se modificó.")
        if enabled:
            if not self.pythonw.is_file() or not self.script.is_file():
                raise RuntimeError("No se encontró el intérprete gráfico o la aplicación.")
            if len(self.command) > 260:
                raise RuntimeError("La ruta de inicio supera el límite de Windows de 260 caracteres.")
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, self.NAME, 0, winreg.REG_SZ, self.command)
        elif self.status() == "enabled":
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self.NAME)


class SleepInhibitor:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self) -> None:
        self._active = False
        self._thread_id: int | None = None

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        thread_id = threading.get_ident()
        if self._active and self._thread_id != thread_id:
            raise RuntimeError("La solicitud de energía debe liberarse desde el hilo que la creó.")
        flags = self.ES_CONTINUOUS | (self.ES_SYSTEM_REQUIRED if active else 0)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        function = kernel.SetThreadExecutionState
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        if not function(flags):
            raise ctypes.WinError(ctypes.get_last_error())
        self._active = active
        self._thread_id = thread_id if active else None
