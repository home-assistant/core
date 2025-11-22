"""Test the Essent sensors."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from essent_dynamic_pricing.models import EnergyData, EssentPrices
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from homeassistant.components.essent.sensor import (
    _format_dt_str,
    _parse_tariff_datetime,
)
from tests.common import MockConfigEntry, async_fire_time_changed

from . import setup_integration

pytestmark = [
    pytest.mark.usefixtures("entity_registry_enabled_by_default"),
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


async def test_sensor_states(hass: HomeAssistant) -> None:
    """Test the sensor states and attributes."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_next_price", "gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    elec_current = _state("electricity_current_price")
    elec_next = _state("electricity_next_price")
    gas_current = _state("gas_current_price")
    gas_next = _state("gas_next_price")

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


async def test_average_price_sensors(
    hass: HomeAssistant, patch_essent_client: AsyncMock
) -> None:
    """Test average price sensors for electricity and gas."""
    patch_essent_client.async_get_prices.return_value = EssentPrices(
        electricity=EnergyData(
            tariffs=[],
            tariffs_tomorrow=[],
            unit="kWh",
            min_price=0.1,
            avg_price=0.123,
            max_price=0.9,
        ),
        gas=EnergyData(
            tariffs=[],
            tariffs_tomorrow=[],
            unit="m³",
            min_price=0.2,
            avg_price=0.678,
            max_price=1.2,
        ),
    )

    await setup_integration(hass)
    ent_reg = er.async_get(hass)

    elec_id = ent_reg.async_get_entity_id(
        "sensor", "essent", "electricity_average_today"
    )
    gas_id = ent_reg.async_get_entity_id("sensor", "essent", "gas_average_today")
    assert elec_id is not None
    assert gas_id is not None

    elec = hass.states.get(elec_id)
    gas = hass.states.get(gas_id)
    assert elec is not None
    assert gas is not None

    assert float(elec.state) == 0.123
    assert elec.attributes["unit_of_measurement"] == "€/kWh"
    assert float(gas.state) == 0.678
    assert gas.attributes["unit_of_measurement"] == "€/m³"


async def test_sensor_states_with_different_timezone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors still match tariffs when HA timezone differs."""
    await hass.config.async_set_time_zone("America/New_York")
    await hass.async_block_till_done()
    freezer.move_to("2025-11-16 04:30:00-05:00")

    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_next_price", "gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    elec_current = _state("electricity_current_price")
    elec_next = _state("electricity_next_price")

    assert elec_current is not None
    assert float(elec_current.state) == 0.25

    assert elec_next is not None
    assert float(elec_next.state) == 0.22


async def test_sensor_updates_when_time_moves(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors update when time moves forward."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_next_price", "gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    assert float(_state("electricity_current_price").state) == 0.25

    next_listener = dt_util.now().replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    freezer.move_to(next_listener)
    async_fire_time_changed(hass, next_listener)
    await hass.async_block_till_done()

    assert float(_state("electricity_current_price").state) == 0.22

    next_day = dt_util.now() + timedelta(days=1)
    midnight_local = next_day.replace(hour=0, minute=30, second=0, microsecond=0)
    freezer.move_to(midnight_local)
    async_fire_time_changed(hass, midnight_local)
    await hass.async_block_till_done()

    assert float(_state("electricity_current_price").state) == 0.21
    assert _state("electricity_next_price").state == STATE_UNKNOWN


async def test_gas_next_price_missing_tomorrow_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    patch_essent_client: AsyncMock,
    partial_gas_normalized_data: EssentPrices,
) -> None:
    """Gas next price should be unknown when tomorrow's tariffs are missing."""
    freezer.move_to("2025-11-21 00:30:00+01:00")
    patch_essent_client.async_get_prices.return_value = partial_gas_normalized_data

    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_next_price", "gas_next_price"),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    gas_current = _state("gas_current_price")
    assert float(gas_current.state) == pytest.approx(1.1457)
    assert gas_current.attributes["unit_of_measurement"] == "€/m³"

    gas_next = _state("gas_next_price")
    assert gas_next.state == STATE_UNKNOWN

    elec_next = _state("electricity_next_price")
    assert float(elec_next.state) == pytest.approx(0.24679)


async def test_electricity_lowest_price_sensor(
    hass: HomeAssistant,
) -> None:
    """Test lowest price sensor for electricity."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_lowest_price_today",),
    )

    entity_id = ent_reg.async_get_entity_id(
        "sensor", "essent", "electricity_lowest_price_today"
    )
    assert entity_id is not None
    sensor = hass.states.get(entity_id)
    assert sensor is not None
    assert float(sensor.state) == 0.2


async def test_electricity_highest_price_sensor(
    hass: HomeAssistant,
) -> None:
    """Test highest price sensor for electricity."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        ("electricity_highest_price_today",),
    )

    entity_id = ent_reg.async_get_entity_id(
        "sensor", "essent", "electricity_highest_price_today"
    )
    assert entity_id is not None
    sensor = hass.states.get(entity_id)
    assert sensor is not None
    assert float(sensor.state) == 0.25


async def test_sensors_handle_empty_tariffs(
    hass: HomeAssistant, patch_essent_client
) -> None:
    """Sensors should return None/{} when no tariffs are present."""
    patch_essent_client.async_get_prices.return_value = EssentPrices(
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
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)
    await _enable_unique_ids(
        hass,
        entry,
        ent_reg,
        (
            "electricity_next_price",
            "electricity_lowest_price_today",
            "electricity_highest_price_today",
        ),
    )

    def _state(unique_id: str):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state

    assert _state("electricity_current_price").state == STATE_UNKNOWN
    assert _state("electricity_next_price").state == STATE_UNKNOWN

    lowest = _state("electricity_lowest_price_today")
    highest = _state("electricity_highest_price_today")

    assert float(lowest.state) == 0
    assert float(highest.state) == 0
    assert lowest.attributes["unit_of_measurement"] == "€/kWh"
    assert highest.attributes["unit_of_measurement"] == "€/kWh"


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
    hass: HomeAssistant,
) -> None:
    """Current price breakdown sensors are disabled by default and return values when enabled."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)

    breakdown_unique_ids = (
        "electricity_current_price_ex_vat",
        "electricity_current_price_vat",
        "electricity_current_price_market_price",
        "electricity_current_price_purchasing_fee",
        "electricity_current_price_tax",
        "gas_current_price_ex_vat",
        "gas_current_price_vat",
        "gas_current_price_market_price",
        "gas_current_price_purchasing_fee",
        "gas_current_price_tax",
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
