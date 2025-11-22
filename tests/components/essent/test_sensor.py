"""Test the Essent sensors."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest

from essent_dynamic_pricing.models import EnergyData, EssentPrices
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from homeassistant.components.essent.sensor import (
    EssentAveragePriceSensor,
    EssentCurrentPriceSensor,
    EssentHighestPriceSensor,
    EssentLowestPriceSensor,
    EssentNextPriceSensor,
    _format_dt_str,
    _parse_tariff_datetime,
)
from homeassistant.components.essent.const import (
    ENERGY_TYPE_ELECTRICITY,
    ENERGY_TYPE_GAS,
)
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from tests.common import MockConfigEntry
from . import setup_integration

pytestmark = [
    pytest.mark.usefixtures(
        "entity_registry_enabled_by_default", "disable_coordinator_schedules"
    ),
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
]


async def test_sensor_states(
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test the sensor states and attributes."""
    await setup_integration(hass, essent_api_response)

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


async def test_sensor_states_with_different_timezone(
    hass: HomeAssistant,
    essent_api_response: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors still match tariffs when HA timezone differs."""
    await hass.config.async_set_time_zone("America/New_York")
    await hass.async_block_till_done()
    freezer.move_to("2025-11-16 04:30:00-05:00")

    await setup_integration(hass, essent_api_response)

    elec_current = hass.states.get("sensor.essent_electricity_current_price")
    elec_next = hass.states.get("sensor.essent_electricity_next_price")

    assert elec_current is not None
    assert float(elec_current.state) == 0.25

    assert elec_next is not None
    assert float(elec_next.state) == 0.22


async def test_sensor_updates_when_time_moves(
    hass: HomeAssistant,
    essent_api_response: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors update when time moves forward."""
    entry = await setup_integration(hass, essent_api_response)
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
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test lowest price sensor for electricity."""
    entry = await setup_integration(hass, essent_api_response)
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
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test highest price sensor for electricity."""
    entry = await setup_integration(hass, essent_api_response)
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


async def test_sensors_handle_missing_data(hass: HomeAssistant) -> None:
    """Sensors should handle missing coordinator data gracefully."""
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)
    coordinator.data = None

    current = EssentCurrentPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    next_sensor = EssentNextPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    avg = EssentAveragePriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    low = EssentLowestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    high = EssentHighestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)

    assert current.native_value is None
    assert next_sensor.native_value is None
    assert avg.native_value is None
    assert low.native_value is None
    assert high.native_value is None
    assert current.native_unit_of_measurement == "€/kWh"
    assert next_sensor.native_unit_of_measurement == "€/kWh"
    assert avg.native_unit_of_measurement == "€/kWh"
    assert low.native_unit_of_measurement == "€/kWh"
    assert high.native_unit_of_measurement == "€/kWh"
    assert current.extra_state_attributes == {}
    assert next_sensor.extra_state_attributes == {}
    assert avg.extra_state_attributes == {}
    assert low.extra_state_attributes == {}
    assert high.extra_state_attributes == {}


async def test_sensors_handle_empty_tariffs(hass: HomeAssistant) -> None:
    """Sensors should return None/{} when no tariffs are present."""
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)
    prices = EssentPrices(
        electricity=EnergyData(
            tariffs=[],
            tariffs_tomorrow=[],
            unit="kWh",
            min_price=0,
            avg_price=0,
            max_price=0,
        ),
        gas=EnergyData(
            tariffs=[],
            tariffs_tomorrow=[],
            unit="m³",
            min_price=0,
            avg_price=0,
            max_price=0,
        ),
    )
    coordinator.data = prices

    current = EssentCurrentPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    next_sensor = EssentNextPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    low = EssentLowestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)
    high = EssentHighestPriceSensor(coordinator, ENERGY_TYPE_ELECTRICITY)

    assert current.native_value is None
    assert next_sensor.native_value is None
    assert current.extra_state_attributes == {}
    assert next_sensor.extra_state_attributes == {}
    assert low.extra_state_attributes == {}
    assert high.extra_state_attributes == {}


def test_parse_tariff_datetime_and_formatting() -> None:
    """Ensure helper functions cover edge cases."""
    assert _parse_tariff_datetime(None) is None
    assert _parse_tariff_datetime("invalid") is None

    naive = "2025-11-16T10:00:00"
    parsed = _parse_tariff_datetime(naive)
    assert parsed is not None
    assert parsed.tzinfo is not None

    assert _format_dt_str(None) is None
    assert _format_dt_str("invalid") == "invalid"
    assert _format_dt_str(naive).endswith("+01:00")
