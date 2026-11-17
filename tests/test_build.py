import json
import subprocess
from unittest.mock import patch

import pytest

import build
from app_info import APP_INFO


def test_next_version_and_windows_limit():
    assert build.next_version("1.2.9") == "1.2.10"
    for version in ("1.2", "1.02.3", "1.2.65535", "-1.0.0"):
        with pytest.raises(ValueError):
            build.next_version(version)


def test_build_publishes_then_updates_version(tmp_path, monkeypatch):
    info_path = tmp_path / "app_info.json"
    info_path.write_text(json.dumps({**APP_INFO, "version": "2.0.0"}), encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "INFO_PATH", info_path)
    monkeypatch.setattr(build, "copy_license_notices", lambda package: None)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "-m" in command:
            dist = command[command.index("--distpath") + 1]
            from pathlib import Path
            package = Path(dist) / "OpenHotspot"
            package.mkdir(parents=True)
            (package / "OpenHotspot.exe").touch()
        else:
            assert command[-1] == "--verify-bundle"
            assert json.loads(info_path.read_text(encoding="utf-8"))["version"] == "2.0.0"

    with patch("build.subprocess.run", side_effect=run):
        result = build.build()
    assert result.name == "OpenHotspot-2.0.1"
    assert (result / "OpenHotspot.exe").is_file()
    assert json.loads(info_path.read_text(encoding="utf-8"))["version"] == "2.0.1"
    assert len(calls) == 2
    with pytest.raises(FileExistsError):
        info_path.write_text(json.dumps({**APP_INFO, "version": "2.0.0"}), encoding="utf-8")
        build.build()


def test_license_notices_include_project_and_runtime_licenses(tmp_path):
    build.copy_license_notices(tmp_path)
    assert (tmp_path / "LICENSE").is_file()
    index = (tmp_path / "THIRD_PARTY_LICENSES" / "INDEX.txt").read_text(encoding="utf-8")
    assert "customtkinter" in index.lower()
    assert "requests" in index.lower()


def test_failed_build_does_not_increment_version(tmp_path, monkeypatch):
    info_path = tmp_path / "app_info.json"
    original = json.dumps({**APP_INFO, "version": "2.0.0"})
    info_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "INFO_PATH", info_path)
    with patch("build.subprocess.run", side_effect=subprocess.CalledProcessError(1, "PyInstaller")):
        with pytest.raises(subprocess.CalledProcessError):
            build.build()
    assert info_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "dist" / "OpenHotspot-2.0.1").exists()
