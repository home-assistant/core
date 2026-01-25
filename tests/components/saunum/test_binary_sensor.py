"""Test the Saunum binary sensor platform."""

from __future__ import annotations

from dataclasses import replace

from freezegun.api import FrozenDateTimeFactory
from pysaunum import SaunumException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_not_created_when_value_is_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test binary sensors are not created when initial value is None."""
    base_data = mock_saunum_client.async_get_data.return_value
    mock_saunum_client.async_get_data.return_value = replace(
        base_data,
        door_open=None,
        alarm_door_open=None,
        alarm_door_sensor=None,
        alarm_thermal_cutoff=None,
        alarm_internal_temp=None,
        alarm_temp_sensor_short=None,
        alarm_temp_sensor_open=None,
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.saunum_leil_door") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_door_open") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_door_sensor") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_thermal_cutoff") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_internal_temp") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_temp_sensor_short") is None
    assert hass.states.get("binary_sensor.saunum_leil_alarm_temp_sensor_open") is None


@pytest.mark.usefixtures("init_integration")
async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_saunum_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entity becomes unavailable when coordinator update fails."""
    entity_id = "binary_sensor.saunum_leil_door"

    # Verify entity is initially available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Make the next update fail
    mock_saunum_client.async_get_data.side_effect = SaunumException("Read error")

    # Move time forward to trigger a coordinator update (60 seconds)
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entity should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
