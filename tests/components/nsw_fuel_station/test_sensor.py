"""The tests for the NSW Fuel Station sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")
pytestmark = pytest.mark.usefixtures("init_integration")


async def test_sensor_values(
    hass: HomeAssistant,
    mock_fuelcheckclient: MagicMock,
) -> None:
    """Test retrieval of sensor values."""
    assert hass.states.get("sensor.joe_s_servo_e10").state == "155.2"
    assert hass.states.get("sensor.joe_s_servo_dl").state == "165.5"
