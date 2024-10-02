"""Tests for the BSB-Lan sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_CURRENT_TEMP = "sensor.bsb_lan_current_temperature"
ENTITY_OUTSIDE_TEMP = "sensor.bsb_lan_outside_temperature"


async def test_sensor_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("value", "expected_state"),
    [
        (18.6, "18.6"),
        (None, STATE_UNKNOWN),
        ("---", STATE_UNKNOWN),
    ],
)
async def test_current_temperature_scenarios(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    value,
    expected_state,
) -> None:
    """Test various scenarios for current temperature sensor."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Set up the mock value
    mock_current_temp = MagicMock()
    mock_current_temp.value = value
    mock_bsblan.sensor.return_value.current_temperature = mock_current_temp

    # Trigger an update
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check the state
    state = hass.states.get(ENTITY_CURRENT_TEMP)
    assert state.state == expected_state
