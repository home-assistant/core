"""Test the Motion Blinds config flow."""
from unittest.mock import Mock

from motionblinds import DEVICE_TYPES_WIFI, BlindType

from homeassistant.components.motion_blinds.gateway import device_name
from homeassistant.core import HomeAssistant

TEST_BLIND_MAC = "abcdefghujkl0001"


async def test_device_name(hass: HomeAssistant) -> None:
    """test_device_name."""
    blind = Mock()
    blind.blind_type = BlindType.RollerBlind.name
    blind.mac = TEST_BLIND_MAC
    assert device_name(blind) == "RollerBlind 0001"

    blind.device_type = DEVICE_TYPES_WIFI[0]
    assert device_name(blind) == "RollerBlind"
