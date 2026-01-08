"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setting up the sensor platform."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity IDs are generated from translation keys
    state = hass.states.get("sensor.openevse_charging_status")
    assert state is not None
    assert state.state == "Charging"
    entry = entity_registry.async_get("sensor.openevse_charging_status")
    assert entry
    assert entry.unique_id == "deadbeeffeed_status"

    state = hass.states.get("sensor.openevse_charge_time_elapsed")
    assert state is not None
    assert state.state == "60.0"
    entry = entity_registry.async_get("sensor.openevse_charge_time_elapsed")
    assert entry
    assert entry.unique_id == "deadbeeffeed_charge_time"

    state = hass.states.get("sensor.openevse_ambient_temperature")
    assert state is not None
    assert state.state == "25.5"
    entry = entity_registry.async_get("sensor.openevse_ambient_temperature")
    assert entry
    assert entry.unique_id == "deadbeeffeed_ambient_temp"

    state = hass.states.get("sensor.openevse_usage_this_session")
    assert state is not None
    assert state.state == "15.0"
    entry = entity_registry.async_get("sensor.openevse_usage_this_session")
    assert entry
    assert entry.unique_id == "deadbeeffeed_usage_session"

    state = hass.states.get("sensor.openevse_total_usage")
    assert state is not None
    assert state.state == "500.0"
    entry = entity_registry.async_get("sensor.openevse_total_usage")
    assert entry
    assert entry.unique_id == "deadbeeffeed_usage_total"

    # Disabled by default entities
    state = hass.states.get("sensor.openevse_ir_temperature")
    assert state is None

    state = hass.states.get("sensor.openevse_rtc_temperature")
    assert state is None
