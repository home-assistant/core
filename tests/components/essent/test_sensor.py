"""Test the Essent sensors."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = [
    pytest.mark.usefixtures(
        "entity_registry_enabled_by_default", "disable_coordinator_schedules"
    ),
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
]


async def test_sensor_states(
    hass: HomeAssistant, aioclient_mock, essent_api_response: dict
) -> None:
    """Test the sensor states and attributes."""
    await setup_integration(hass, aioclient_mock, essent_api_response)

    elec_current = hass.states.get("sensor.essent_electricity_current_price")
    elec_next = hass.states.get("sensor.essent_electricity_next_price")
    gas_current = hass.states.get("sensor.essent_gas_current_price")
    gas_next = hass.states.get("sensor.essent_gas_next_price")

    assert elec_current is not None
    assert float(elec_current.state) == 0.25
    assert elec_current.attributes["unit_of_measurement"] == "€/kWh"
    assert elec_current.attributes["market_price"] == 0.17
    assert elec_current.attributes["purchasing_fee"] == 0.03
    assert elec_current.attributes["tax"] == 0.05

    assert elec_next is not None
    assert float(elec_next.state) == 0.22
    assert elec_next.attributes["unit_of_measurement"] == "€/kWh"

    assert gas_current is not None
    assert float(gas_current.state) == 0.82
    assert gas_current.attributes["unit_of_measurement"] == "€/m³"

    assert gas_next is not None
    assert float(gas_next.state) == 0.78
    assert gas_next.attributes["unit_of_measurement"] == "€/m³"


async def test_sensor_updates_when_time_moves(
    hass: HomeAssistant,
    aioclient_mock,
    essent_api_response: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors update when time moves forward."""
    entry = await setup_integration(hass, aioclient_mock, essent_api_response)
    coordinator = entry.runtime_data

    # Move within today's tariffs
    freezer.move_to("2025-11-16 11:30:00+01:00")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    elec_current = hass.states.get("sensor.essent_electricity_current_price")
    assert elec_current is not None
    assert float(elec_current.state) == 0.22

    # Move into tomorrow's tariffs
    freezer.move_to("2025-11-17 00:30:00+01:00")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    elec_current = hass.states.get("sensor.essent_electricity_current_price")
    elec_next = hass.states.get("sensor.essent_electricity_next_price")

    assert elec_current is not None
    assert float(elec_current.state) == 0.21
    assert elec_next is not None
    assert elec_next.state == STATE_UNKNOWN


async def test_electricity_lowest_price_sensor(
    hass: HomeAssistant, aioclient_mock, essent_api_response: dict
) -> None:
    """Test lowest price sensor for electricity."""
    entry = await setup_integration(hass, aioclient_mock, essent_api_response)
    entity_id = "sensor.essent_electricity_lowest_price_today"
    ent_reg = er.async_get(hass)
    reg_entry = ent_reg.async_get(entity_id)
    assert reg_entry is not None
    ent_reg.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.essent_electricity_lowest_price_today")
    assert sensor is not None
    assert float(sensor.state) == 0.2
    assert "09:00:00" in sensor.attributes["start"]
    assert "10:00:00" in sensor.attributes["end"]


async def test_electricity_highest_price_sensor(
    hass: HomeAssistant, aioclient_mock, essent_api_response: dict
) -> None:
    """Test highest price sensor for electricity."""
    entry = await setup_integration(hass, aioclient_mock, essent_api_response)
    entity_id = "sensor.essent_electricity_highest_price_today"
    ent_reg = er.async_get(hass)
    reg_entry = ent_reg.async_get(entity_id)
    assert reg_entry is not None
    ent_reg.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.essent_electricity_highest_price_today")
    assert sensor is not None
    assert float(sensor.state) == 0.25
    assert "10:00:00" in sensor.attributes["start"]
    assert "11:00:00" in sensor.attributes["end"]
