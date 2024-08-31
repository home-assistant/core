"""Fixtures for the Blink integration tests."""

from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
from uuid import uuid4

import blinkpy
import pytest

from homeassistant.components.blink.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

CAMERA_ATTRIBUTES = {
    "name": "Camera 1",
    "camera_id": "111111",
    "serial": "serial",
    "temperature": None,
    "temperature_c": 25.1,
    "temperature_calibrated": None,
    "battery": "ok",
    "battery_voltage": None,
    "thumbnail": "https://rest-u034.immedia-semi.com/api/v3/media/accounts/111111/networks/222222/lotus/333333/thumbnail/thumbnail.jpg?ts=1698141602&ext=",
    "video": None,
    "recent_clips": [],
    "motion_enabled": True,
    "motion_detected": False,
    "wifi_strength": None,
    "network_id": 222222,
    "sync_module": "sync module",
    "last_record": None,
    "type": "lotus",
}


@pytest.fixture
def camera() -> MagicMock:
    """Set up a Blink camera fixture."""
    mock_blink_camera = create_autospec(blinkpy.camera.BlinkCamera, instance=True)
    mock_blink_camera.sync = AsyncMock(return_value=True)
    mock_blink_camera.name = "Camera 1"
    mock_blink_camera.camera_id = "111111"
    mock_blink_camera.serial = "12345"
    mock_blink_camera.motion_enabled = True
    mock_blink_camera.temperature = 25.1
    mock_blink_camera.motion_detected = False
    mock_blink_camera.wifi_strength = 2.1
    mock_blink_camera.camera_type = "lotus"
    mock_blink_camera.version = "123"
    mock_blink_camera.attributes = CAMERA_ATTRIBUTES
    return mock_blink_camera


@pytest.fixture(name="mock_blink_api")
def blink_api_fixture(camera) -> MagicMock:
    """Set up Blink API fixture."""
    mock_blink_api = create_autospec(blinkpy.blinkpy.Blink, instance=True)
    mock_blink_api.available = True
    mock_blink_api.start = AsyncMock(return_value=True)
    mock_blink_api.refresh = AsyncMock(return_value=True)
    mock_blink_api.sync = MagicMock(return_value=True)
    mock_blink_api.cameras = {camera.name: camera}
    mock_blink_api.request_homescreen = AsyncMock(return_value=True)

    with patch("homeassistant.components.blink.Blink") as class_mock:
        class_mock.return_value = mock_blink_api
        yield mock_blink_api


@pytest.fixture(name="mock_blink_auth_api")
def blink_auth_api_fixture() -> MagicMock:
    """Set up Blink API fixture."""
    mock_blink_auth_api = create_autospec(blinkpy.auth.Auth, instance=True)
    mock_blink_auth_api.check_key_required.return_value = False
    mock_blink_auth_api.send_auth_key = AsyncMock(return_value=True)

    with patch("homeassistant.components.blink.Auth", autospec=True) as class_mock:
        class_mock.return_value = mock_blink_auth_api
        yield mock_blink_auth_api


@pytest.fixture(name="mock_config_entry")
def mock_config_fixture():
    """Return a fake config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "Password",
            "device_id": "Home Assistant",
            "uid": "BlinkCamera_e1233333e2-0909-09cd-777a-123456789012",
            "token": "A_token",
            "unique_id": "an_email@email.com",
            "host": "u034.immedia-semi.com",
            "region_id": "u034",
            "client_id": 123456,
            "account_id": 654321,
        },
        entry_id=str(uuid4()),
        version=3,
    )
