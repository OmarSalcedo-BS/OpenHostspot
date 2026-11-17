"""Genera una distribución gráfica de Windows y actualiza su versión."""

import json
import importlib.metadata
import msvcrt
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from packaging.requirements import Requirement

from app_info import INFO_PATH, load_app_info


ROOT = Path(__file__).resolve().parent
RUNTIME_DISTRIBUTIONS = (
    "customtkinter", "qrcode", "pillow", "pywin32", "comtypes", "psutil", "requests",
    "winrt-Windows.Devices.WiFiDirect", "winrt-Windows.Devices.Enumeration",
    "winrt-Windows.Security.Credentials", "winrt-Windows.Networking", "pyinstaller",
)


def next_version(version: str) -> str:
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError(f"Versión no válida: {version}. Usa major.minor.patch.")
    parts = [int(part) for part in version.split(".")]
    parts[2] += 1
    if any(part > 65535 for part in parts):
        raise ValueError("Los componentes de versión de Windows no pueden superar 65535.")
    return ".".join(map(str, parts))


def version_resource(info: dict[str, str]) -> str:
    version = tuple(int(part) for part in info["version"].split(".")) + (0,)
    fields = {
        "CompanyName": info["author"],
        "FileDescription": info["description"],
        "FileVersion": info["version"],
        "InternalName": info["name"],
        "LegalCopyright": info["copyright"],
        "OriginalFilename": "OpenHotspot.exe",
        "ProductName": info["name"],
        "ProductVersion": info["version"],
    }
    strings = ",\n".join(f"StringStruct({key!r}, {value!r})" for key, value in fields.items())
    return (
        "VSVersionInfo(ffi=FixedFileInfo("
        f"filevers={version!r}, prodvers={version!r}, mask=0x3f, flags=0, OS=0x40004, "
        "fileType=1, subtype=0, date=(0, 0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        f"{strings}"
        "])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])"
    )


def copy_license_notices(package: Path) -> None:
    shutil.copy2(ROOT / "LICENSE", package / "LICENSE")
    notices = package / "THIRD_PARTY_LICENSES"
    notices.mkdir()
    pending = list(RUNTIME_DISTRIBUTIONS)
    seen: set[str] = set()
    lines = ["Licencias disponibles de dependencias instaladas (incluye dependencias transitivas):", ""]
    while pending:
        distribution = importlib.metadata.distribution(pending.pop())
        name = distribution.metadata["Name"]
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        for dependency in distribution.requires or ():
            requirement = Requirement(dependency)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
        files = []
        for entry in distribution.files or ():
            parts = entry.parts
            if not parts or not parts[0].endswith(".dist-info"):
                continue
            relative = Path(*parts[1:])
            if (not any(part.lower() == "licenses" for part in relative.parts)
                    and not relative.name.lower().startswith(("license", "copying", "notice"))):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                target = notices / normalized / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                files.append(str(target.relative_to(notices)))
        expression = distribution.metadata.get("License-Expression") or distribution.metadata.get("License") or "No indicada"
        lines.append(f"{name} {distribution.version} | {expression.splitlines()[0]} | "
                     f"{', '.join(files) if files else 'Sin archivo de licencia en los metadatos instalados'}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, notices / "Python-LICENSE.txt")
        lines.append("Python | Python-LICENSE.txt")
    else:
        lines.append("Python | No se encontró LICENSE.txt en la instalación de Python.")
    (notices / "INDEX.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build() -> Path:
    lock_path = ROOT / ".build.lock"
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("Ya hay una compilación en curso.") from error
        try:
            return _build_locked()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _build_locked() -> Path:
    original = INFO_PATH.read_bytes()
    info = load_app_info(INFO_PATH)
    info["version"] = next_version(info["version"])
    destination = ROOT / "dist" / f"OpenHotspot-{info['version']}"
    if destination.exists():
        raise FileExistsError(f"La distribución ya existe: {destination}. No se sobrescribirá.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".openhotspot-build-", dir=destination.parent) as directory:
        temp = Path(directory)
        metadata = temp / "app_info.json"
        metadata.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        version_file = temp / "version.txt"
        version_file.write_text(version_resource(info), encoding="utf-8")
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
            "--name", "OpenHotspot", "--distpath", str(temp / "dist"),
            "--workpath", str(temp / "work"), "--specpath", str(temp),
            "--collect-all", "customtkinter", "--collect-all", "comtypes",
            "--collect-submodules", "winrt.windows",
            "--add-data", f"{metadata};.", "--add-data", f"{ROOT / 'LICENSE'};.",
            "--version-file", str(version_file), str(ROOT / "gui.pyw"),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        package = temp / "dist" / "OpenHotspot"
        executable = package / "OpenHotspot.exe"
        if not executable.is_file():
            raise RuntimeError(f"No se generó el ejecutable esperado: {executable}")
        copy_license_notices(package)
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(temp / "profile")
        subprocess.run([str(executable), "--verify-bundle"], cwd=package, env=environment,
                       check=True, timeout=60)
        if INFO_PATH.read_bytes() != original:
            raise RuntimeError("La información de la aplicación cambió durante la compilación; no se publicó.")
        try:
            shutil.copytree(package, destination)
        except OSError as error:
            raise RuntimeError(
                f"No se pudo copiar la distribución a {destination}: {error}. "
                "La versión no se incrementó; revisa si quedó una carpeta incompleta."
            ) from error
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=ROOT, prefix=".app-info-",
                                             suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                file.write(metadata.read_bytes())
                file.flush()
                os.fsync(file.fileno())
            try:
                os.replace(temporary, INFO_PATH)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as error:
            raise RuntimeError(
                f"Se creó {destination}, pero no se pudo actualizar {INFO_PATH}: {error}. "
                "La versión no se incrementó; mueve o elimina esa distribución antes de reintentar."
            ) from error
    return destination


def main() -> int:
    try:
        destination = build()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Error al generar OpenHotspot: {error}", file=sys.stderr)
        return 1
    print(f"Distribución creada: {destination}")
    print(f"Ejecutable: {destination / 'OpenHotspot.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
