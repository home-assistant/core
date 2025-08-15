"""Test Snoo Sensors."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.snoo.sensor import async_setup_entry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA


async def test_sensors(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test sensors and check test values are correctly set."""
    await async_init_integration(hass)
    # 2 device sensors + 3 baby sensors = 5 total
    assert len(hass.states.async_all("sensor")) == 5
    assert hass.states.get("sensor.test_snoo_state").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_snoo_time_left").state == STATE_UNAVAILABLE
    find_update_callback(bypass_api, "random_num")(MOCK_SNOO_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 5
    assert hass.states.get("sensor.test_snoo_state").state == "stop"
    assert hass.states.get("sensor.test_snoo_time_left").state == STATE_UNKNOWN


async def test_baby_sensor_with_baby_coordinators(hass: HomeAssistant) -> None:
    """Test baby sensor setup with baby coordinators."""
    mock_entry = MagicMock()

    # Mock coordinator with baby coordinators
    mock_coordinator = MagicMock()
    mock_coordinator.baby_coordinators = {
        "baby1": MagicMock(),
        "baby2": MagicMock(),
    }

    mock_entry.runtime_data = {"coordinator1": mock_coordinator}

    async_add_entities = AsyncMock()

    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Verify entities were added
    assert async_add_entities.call_count == 1
    # The call should contain a list of sensors
    call_args = async_add_entities.call_args[0][0]
    # 2 device sensors + (2 babies × 3 sensors) = 2 + 6 = 8 total
    assert len(call_args) == 8
