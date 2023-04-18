"""The tests for the Ring sensor platform."""
import requests_mock

from homeassistant.core import HomeAssistant

from .common import setup_platform

WIFI_ENABLED = False


async def test_sensor(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the Ring buttons."""
    await setup_platform(hass, "button")

    front_door_state = hass.states.get("button.front_door_intercom_open_door")
    assert front_door_state is not None

