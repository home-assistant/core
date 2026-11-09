"""Tests for the Telldus Live binary sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant


@pytest.fixture
def device(mock_tellduslive: MagicMock) -> MagicMock:
    """Return a mocked device without any controllable methods."""
    device = mock_tellduslive.devices[0]
    device.methods = 0
    device.is_on = True
    return device


@pytest.mark.usefixtures("setup_integration")
async def test_binary_sensor_state(hass: HomeAssistant) -> None:
    """Test a device without methods becomes a binary sensor."""
    assert hass.states.get("binary_sensor.kitchen").state == STATE_ON
