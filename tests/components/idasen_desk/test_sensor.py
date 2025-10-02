"""Test the IKEA Idasen Desk sensors."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import UPDATE_DEBOUNCE_TIME, init_integration

from tests.common import async_fire_time_changed

EXPECTED_INITIAL_HEIGHT = "1"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_height_sensor(
    hass: HomeAssistant, mock_desk_api: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test height sensor."""
    await init_integration(hass)

    entity_id = "sensor.test_height"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == EXPECTED_INITIAL_HEIGHT

    mock_desk_api.height = 1.2
    mock_desk_api.trigger_update_callback(None)
    await hass.async_block_till_done()

    # Initial state should still be the same due to debounce
    state = hass.states.get(entity_id)
    assert state
    assert state.state == EXPECTED_INITIAL_HEIGHT

    freezer.tick(UPDATE_DEBOUNCE_TIME)
    async_fire_time_changed(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1.2"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_available(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor available property."""
    await init_integration(hass)

    entity_id = "sensor.test_height"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == EXPECTED_INITIAL_HEIGHT

    mock_desk_api.is_connected = False
    mock_desk_api.trigger_update_callback(None)

    freezer.tick(UPDATE_DEBOUNCE_TIME)
    async_fire_time_changed(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE
