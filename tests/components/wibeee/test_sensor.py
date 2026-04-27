"""Tests for Wibeee sensors."""

from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that sensor entities are created."""
    states = hass.states.async_all("sensor")
    # Should have sensors for the discovered phases
    entity_ids = {state.entity_id for state in states}
    assert "sensor.wibeee_2233_active_power" in entity_ids
    assert "sensor.wibeee_2233_l1_active_power" in entity_ids


async def test_sensor_state_class(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor has correct state class."""
    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.attributes.get("state_class") == "measurement"


async def test_sensor_no_data(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor handles missing data."""
    # Wipe coordinator data
    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_invalid_value(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor handles non-numeric values."""
    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator

    # Inject non-numeric data
    invalid_data = {
        "fase4": {
            "p_activa": "not_a_number",
        }
    }
    coordinator.async_set_updated_data(invalid_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.state == STATE_UNAVAILABLE
