"""Test the Essent sensors."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest

from essent_dynamic_pricing.models import EnergyData, EssentPrices
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from homeassistant.components.essent import sensor as essent_sensor
from homeassistant.components.essent.sensor import (
    EssentSensor,
    _format_dt_str,
    _parse_tariff_datetime,
)
from homeassistant.components.essent.const import EnergyType
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from tests.common import MockConfigEntry
from . import setup_integration

_DESCS = {desc.key: desc for desc in essent_sensor.SENSORS}

pytestmark = [
    pytest.mark.usefixtures(
        "entity_registry_enabled_by_default", "disable_coordinator_schedules"
    ),
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
]


async def _enable_unique_ids(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    ent_reg: er.EntityRegistry,
    unique_ids: tuple[str, ...],
) -> None:
    """Enable disabled entities and reload when needed."""
    updated = False
    for unique_id in unique_ids:
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        reg_entry = ent_reg.async_get(entity_id)
        assert reg_entry is not None
        if reg_entry.disabled_by:
            ent_reg.async_update_entity(entity_id, disabled_by=None)
            updated = True

    if updated:
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()


async def test_sensor_states(hass: HomeAssistant, essent_api_response: dict) -> None:
    """Test the sensor states and attributes."""
    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("essent_electricity_next_price", "essent_gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    elec_current = _state("essent_electricity_current_price")
    elec_next = _state("essent_electricity_next_price")
    gas_current = _state("essent_gas_current_price")
    gas_next = _state("essent_gas_next_price")

    assert elec_current is not None
    assert float(elec_current.state) == 0.25
    assert elec_current.attributes["unit_of_measurement"] == "€/kWh"

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

    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("essent_electricity_next_price", "essent_gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    elec_current = _state("essent_electricity_current_price")
    elec_next = _state("essent_electricity_next_price")

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
    ent_reg = er.async_get(hass)
    coordinator = entry.runtime_data
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("essent_electricity_next_price", "essent_gas_next_price"),
    )

    # Move within today's tariffs
    freezer.move_to("2025-11-16 11:30:00+01:00")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = ent_reg.async_get_entity_id("sensor", "essent", "essent_electricity_current_price")
    assert entity_id is not None
    elec_current = hass.states.get(entity_id)
    assert elec_current is not None
    assert float(elec_current.state) == 0.22

    # Move into tomorrow's tariffs
    freezer.move_to("2025-11-17 00:30:00+01:00")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id_current = ent_reg.async_get_entity_id(
        "sensor", "essent", "essent_electricity_current_price"
    )
    entity_id_next = ent_reg.async_get_entity_id(
        "sensor", "essent", "essent_electricity_next_price"
    )
    assert entity_id_current is not None
    assert entity_id_next is not None
    elec_current = hass.states.get(entity_id_current)
    elec_next = hass.states.get(entity_id_next)

    assert elec_current is not None
    assert float(elec_current.state) == 0.21
    assert elec_next is not None
    assert elec_next.state == STATE_UNKNOWN


async def test_electricity_lowest_price_sensor(
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test lowest price sensor for electricity."""
    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("essent_electricity_lowest_price_today",),
    )

    entity_id = ent_reg.async_get_entity_id(
        "sensor", "essent", "essent_electricity_lowest_price_today"
    )
    assert entity_id is not None
    sensor = hass.states.get(entity_id)
    assert sensor is not None
    assert float(sensor.state) == 0.2


async def test_electricity_highest_price_sensor(
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test highest price sensor for electricity."""
    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("essent_electricity_highest_price_today",),
    )

    entity_id = ent_reg.async_get_entity_id(
        "sensor", "essent", "essent_electricity_highest_price_today"
    )
    assert entity_id is not None
    sensor = hass.states.get(entity_id)
    assert sensor is not None
    assert float(sensor.state) == 0.25


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

    current = EssentSensor(
        coordinator, EnergyType.ELECTRICITY, _DESCS["current_price"]
    )
    next_sensor = EssentSensor(
        coordinator, EnergyType.ELECTRICITY, _DESCS["next_price"]
    )
    low = EssentSensor(
        coordinator, EnergyType.ELECTRICITY, _DESCS["lowest_price_today"]
    )
    high = EssentSensor(
        coordinator, EnergyType.ELECTRICITY, _DESCS["highest_price_today"]
    )

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


async def test_current_price_breakdown_sensors(
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Current price breakdown sensors are disabled by default and return values when enabled."""
    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)

    breakdown_unique_ids = (
        "essent_electricity_current_price_ex_vat",
        "essent_electricity_current_price_vat",
        "essent_electricity_current_price_market_price",
        "essent_electricity_current_price_purchasing_fee",
        "essent_electricity_current_price_tax",
        "essent_gas_current_price_ex_vat",
        "essent_gas_current_price_vat",
        "essent_gas_current_price_market_price",
        "essent_gas_current_price_purchasing_fee",
        "essent_gas_current_price_tax",
    )

    breakdown_entities: list[str] = []
    for unique_id in breakdown_unique_ids:
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        breakdown_entities.append(entity_id)
        reg_entry = ent_reg.async_get(entity_id)
        assert reg_entry is not None
        if reg_entry.disabled_by:
            ent_reg.async_update_entity(entity_id, disabled_by=None)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    (
        elec_ex_vat_id,
        elec_vat_id,
        elec_market_id,
        elec_fee_id,
        elec_tax_id,
        gas_ex_vat_id,
        gas_vat_id,
        gas_market_id,
        gas_fee_id,
        gas_tax_id,
    ) = breakdown_entities

    elec_ex_vat = hass.states.get(elec_ex_vat_id)
    elec_vat = hass.states.get(elec_vat_id)
    elec_market = hass.states.get(elec_market_id)
    elec_fee = hass.states.get(elec_fee_id)
    elec_tax = hass.states.get(elec_tax_id)

    assert elec_ex_vat is not None
    assert float(elec_ex_vat.state) == 0.2066
    assert elec_ex_vat.attributes["unit_of_measurement"] == "€/kWh"

    assert elec_vat is not None
    assert float(elec_vat.state) == 0.0434
    assert elec_market is not None
    assert float(elec_market.state) == 0.17
    assert elec_fee is not None
    assert float(elec_fee.state) == 0.03
    assert elec_tax is not None
    assert float(elec_tax.state) == 0.05

    gas_ex_vat = hass.states.get(gas_ex_vat_id)
    gas_vat = hass.states.get(gas_vat_id)
    gas_market = hass.states.get(gas_market_id)
    gas_fee = hass.states.get(gas_fee_id)
    gas_tax = hass.states.get(gas_tax_id)

    assert gas_ex_vat is not None
    assert float(gas_ex_vat.state) == 0.6777
    assert gas_ex_vat.attributes["unit_of_measurement"] == "€/m³"
    assert gas_vat is not None
    assert float(gas_vat.state) == 0.1423
    assert gas_market is not None
    assert float(gas_market.state) == 0.67
    assert gas_fee is not None
    assert float(gas_fee.state) == 0.05
    assert gas_tax is not None
    assert float(gas_tax.state) == 0.1
