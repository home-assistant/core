"""Test the Litter-Robot camera entity."""

from unittest.mock import AsyncMock, MagicMock

from pylitterbot.camera import CameraSession

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

CAMERA_ENTITY_ID = "camera.test_camera"

MOCK_SESSION_DATA = {
    "sessionId": "test-session-id",
    "sessionToken": "test-session-token",
    "sessionExpiration": "2025-12-31T23:59:59.000000Z",
    "turnCredentials": [
        {
            "urls": ["turn:turn.example.com:443?transport=tcp"],
            "username": "turn-user",
            "credential": "turn-pass",
        }
    ],
}


async def test_camera_entity_created(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """Test camera entity is created for LR5 Pro."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    camera = hass.states.get(CAMERA_ENTITY_ID)
    assert camera is not None
    assert camera.state == "streaming"


async def test_camera_not_created_for_standard_lr5(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test camera entity is not created for standard LR5 (no camera)."""
    await setup_integration(hass, mock_account_with_litterrobot_5, CAMERA_DOMAIN)

    camera = hass.states.get("camera.test_camera")
    assert camera is None


async def test_camera_not_created_for_lr3(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test camera entity is not created for LR3."""
    await setup_integration(hass, mock_account, CAMERA_DOMAIN)

    camera = hass.states.get("camera.test_camera")
    assert camera is None
