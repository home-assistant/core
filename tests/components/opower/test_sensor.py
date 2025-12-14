"""Tests for the Opower sensor platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test the creation and values of Opower sensors."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Check electric sensors
    entry = entity_registry.async_get(
        "sensor.elec_account_111111_current_bill_electric_usage_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_111111_elec_usage_to_date"
    state = hass.states.get(
        "sensor.elec_account_111111_current_bill_electric_usage_to_date"
    )
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.state == "100"

    entry = entity_registry.async_get(
        "sensor.elec_account_111111_current_bill_electric_cost_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_111111_elec_cost_to_date"
    state = hass.states.get(
        "sensor.elec_account_111111_current_bill_electric_cost_to_date"
    )
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "USD"
    assert state.state == "20.0"

    # Check gas sensors
    entry = entity_registry.async_get(
        "sensor.gas_account_222222_current_bill_gas_usage_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_222222_gas_usage_to_date"
    state = hass.states.get("sensor.gas_account_222222_current_bill_gas_usage_to_date")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    # Convert 50 CCF to m³
    assert float(state.state) == pytest.approx(50 * 2.83168, abs=1e-3)

    entry = entity_registry.async_get(
        "sensor.gas_account_222222_current_bill_gas_cost_to_date"
    )
    assert entry
    assert entry.unique_id == "pge_222222_gas_cost_to_date"
    state = hass.states.get("sensor.gas_account_222222_current_bill_gas_cost_to_date")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "USD"
    assert state.state == "15.0"
