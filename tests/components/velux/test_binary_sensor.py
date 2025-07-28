"""Tests for the Velux binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_module")
async def test_rain_sensor_state(
    hass: HomeAssistant,
    mock_window: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the rain sensor."""
    mock_config_entry.add_to_hass(hass)

    test_entity_id = "binary_sensor.test_window_rain_sensor"

    with (
        patch("homeassistant.components.velux.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        # setup config entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # simulate no rain detected
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # simulate rain detected
    mock_window.get_limitation.return_value.min_value = 93
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_ON
