import pytest
from unittest.mock import patch, MagicMock
from src.camera import CameraClient, CameraError


BASE = "http://192.168.1.100"
USER = "admin"
PASS = "secret"


def _client():
    return CameraClient(ip="192.168.1.100", username=USER, password=PASS)


def _preset_response(presets):
    mock = MagicMock()
    mock.json.return_value = [
        {"code": 0, "value": {"PtzPreset": presets}}
    ]
    mock.raise_for_status = MagicMock()
    return mock


def test_get_preset_id_by_name():
    client = _client()
    presets = [
        {"id": 1, "name": "home"},
        {"id": 3, "name": "full garden"},
    ]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)) as mock_get:
        preset_id = client.get_preset_id("full garden")
    assert preset_id == 3


def test_get_preset_id_not_found_raises():
    client = _client()
    presets = [{"id": 1, "name": "home"}]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)):
        with pytest.raises(CameraError, match="Preset 'missing' not found"):
            client.get_preset_id("missing")


def test_get_preset_id_not_found_lists_available():
    client = _client()
    presets = [{"id": 1, "name": "home"}, {"id": 2, "name": "driveway"}]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)):
        with pytest.raises(CameraError, match="home.*driveway"):
            client.get_preset_id("missing")


def test_goto_preset_sends_correct_request():
    client = _client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"code": 0}]
    mock_resp.raise_for_status = MagicMock()
    with patch("src.camera.requests.post", return_value=mock_resp) as mock_post:
        client.goto_preset(3)
    call_kwargs = mock_post.call_args
    assert "GotoPreset" in str(call_kwargs)


def test_fetch_snapshot_returns_bytes():
    client = _client()
    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xd8\xff"  # JPEG magic bytes
    mock_resp.raise_for_status = MagicMock()
    with patch("src.camera.requests.get", return_value=mock_resp):
        data = client.fetch_snapshot()
    assert data == b"\xff\xd8\xff"
