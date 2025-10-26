"""Test Prusalink sensors."""

from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_binary_sensor_platform_only():
    """Only setup sensor platform."""
    with patch(
        "homeassistant.components.prusalink.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_no_job(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("binary_sensor.mock_title_mmu")
    assert state is not None
    assert state.state == STATE_OFF
