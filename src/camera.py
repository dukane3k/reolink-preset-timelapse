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
        resp = requests.post(
            f"{self._base}/api.cgi",
            params=self._params(),
            json=[{"cmd": "GetPtzPreset", "action": 1, "param": {"channel": 0}}],
            timeout=self._timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        try:
            presets = body[0]["initial"]["PtzPreset"]
        except (KeyError, IndexError) as exc:
            raise CameraError(f"Unexpected API response: {body!r}") from exc
        for p in presets:
            if p["name"].lower() == name.lower():
                return int(p["id"])
        available = ", ".join(p["name"] for p in presets if not p["name"].startswith("pos"))
        raise CameraError(
            f"Preset '{name}' not found. Available presets: {available}"
        )

    def goto_preset(self, preset_id: int) -> None:
        resp = requests.post(
            f"{self._base}/api.cgi",
            params=self._params(),
            json=[{"cmd": "PtzCtrl", "action": 0, "param": {"channel": 0, "op": "ToPos", "id": preset_id, "speed": 32}}],
            timeout=self._timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        try:
            code = body[0].get("code", -1)
        except (IndexError, AttributeError) as exc:
            raise CameraError(f"Unexpected API response: {body!r}") from exc
        if code != 0:
            raise CameraError(f"PtzCtrl ToPos returned error code {code}")

    def _set_osd_time(self, enable: bool) -> None:
        resp = requests.post(
            f"{self._base}/api.cgi",
            params=self._params(),
            json=[{"cmd": "SetOsd", "action": 0, "param": {"Osd": {"channel": 0, "osdTime": {"enable": int(enable), "pos": "Upper Left"}}}}],
            timeout=self._timeout,
        )
        resp.raise_for_status()

    def fetch_snapshot(self) -> bytes:
        rs = "".join(random.choices(string.ascii_lowercase, k=8))
        resp = requests.get(
            f"{self._base}/cgi-bin/api.cgi",
            params={**self._params(), "cmd": "Snap", "channel": 0, "rs": rs},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
