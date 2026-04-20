"""Tests for the National Grid US sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test that sensor entities are created for each meter."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Electric meter - usage (kWh, no conversion)
    state = hass.states.get("sensor.electric_meter_last_billing_usage")
    assert state is not None
    assert float(state.state) == 500.0

    # Electric meter - cost
    state = hass.states.get("sensor.electric_meter_last_billing_cost")
    assert state is not None
    assert float(state.state) == 120.5

    # Gas meter - usage (CCF converted to m³ by HA)
    state = hass.states.get("sensor.gas_meter_last_billing_usage")
    assert state is not None
    assert float(state.state) > 0

    # Gas meter - cost
    state = hass.states.get("sensor.gas_meter_last_billing_cost")
    assert state is not None
    assert float(state.state) == 45.0
