"""The camera tests for the august platform."""

from homeassistant.const import STATE_IDLE

from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_doorbell_from_fixture,
)


async def test_create_doorbell(hass):
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    doorbell_details = [doorbell_one]
    await _create_august_with_devices(hass, doorbell_details)

    camera_k98gidt45gul_name = hass.states.get("camera.k98gidt45gul_name")
    assert camera_k98gidt45gul_name.state == STATE_IDLE
