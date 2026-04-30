from __future__ import annotations
import random
import string
import requests


class CameraError(Exception):
    pass


class CameraClient:
    def __init__(self, ip: str, username: str, password: str, timeout: int = 10):
        self._base = f"http://{ip}"
        self._auth = {"user": username, "password": password}
        self._timeout = timeout

    def _params(self, **extra) -> dict:
        return {**self._auth, **extra}

    def get_preset_id(self, name: str) -> int:
        resp = requests.get(
            f"{self._base}/api.cgi",
            params={**self._params(), "cmd": "GetPtzPreset", "channel": 0},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        presets = resp.json()[0]["value"]["PtzPreset"]
        for p in presets:
            if p["name"].lower() == name.lower():
                return int(p["id"])
        available = ", ".join(p["name"] for p in presets)
        raise CameraError(
            f"Preset '{name}' not found. Available presets: {available}"
        )

    def goto_preset(self, preset_id: int) -> None:
        resp = requests.post(
            f"{self._base}/api.cgi",
            params=self._params(),
            json=[{"cmd": "GotoPreset", "param": {"channel": 0, "id": preset_id}}],
            timeout=self._timeout,
        )
        resp.raise_for_status()
        code = resp.json()[0].get("code", -1)
        if code != 0:
            raise CameraError(f"GotoPreset returned error code {code}")

    def fetch_snapshot(self) -> bytes:
        rs = "".join(random.choices(string.ascii_lowercase, k=8))
        resp = requests.get(
            f"{self._base}/cgi-bin/api.cgi",
            params={**self._params(), "cmd": "Snap", "channel": 0, "rs": rs},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
