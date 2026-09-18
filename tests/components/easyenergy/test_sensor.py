"""Tests for the sensors provided by the easyEnergy integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from easyenergy import EasyEnergyNoDataError, Electricity
import pytest

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CURRENCY_EURO,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.freeze_time("2026-04-19 13:00:00+00:00")
async def test_energy_usage_today(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the easyEnergy - Energy usage sensors."""
    entry_id = init_integration.entry_id

    # Current usage energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_usage_current_hour_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_usage_current_hour_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_usage_current_hour_price"
    assert state.state == "-0.00226"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Usage Current hour"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Average usage energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_usage_average_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_usage_average_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_usage_average_price"
    assert state.state == "0.09516"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Usage Average - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest usage energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_usage_max_price")
    entry = entity_registry.async_get("sensor.easyenergy_today_energy_usage_max_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_usage_max_price"
    assert state.state == "0.15082"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Usage Highest price - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest usage price time sensor
    state = hass.states.get("sensor.easyenergy_today_energy_usage_highest_price_time")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_usage_highest_price_time"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_usage_highest_price_time"
    assert state.state == "2026-04-19T18:00:00+00:00"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Usage Time of highest price - today"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_today_energy_usage")}
    assert device_entry.manufacturer == "easyEnergy"
    assert device_entry.name == "Energy market price - Usage"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version

    # Usage periods priced equal or lower sensor
    state = hass.states.get(
        "sensor.easyenergy_today_energy_usage_hours_priced_equal_or_lower"
    )
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_usage_hours_priced_equal_or_lower"
    )
    assert entry
    assert state
    assert (
        entry.unique_id == f"{entry_id}_today_energy_usage_hours_priced_equal_or_lower"
    )
    assert state.state == "2"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy market price"
        " - Usage Periods priced equal or lower than current - today"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes


@pytest.mark.freeze_time("2026-04-19 13:00:00+00:00")
async def test_energy_return_today(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the easyEnergy - Energy return sensors."""
    entry_id = init_integration.entry_id

    # Current return energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_return_current_hour_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_return_current_hour_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_return_current_hour_price"
    assert state.state == "-0.00226"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Return Current hour"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Average return energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_return_average_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_return_average_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_return_average_price"
    assert state.state == "0.09516"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Return Average - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest return energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_return_max_price")
    entry = entity_registry.async_get("sensor.easyenergy_today_energy_return_max_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_return_max_price"
    assert state.state == "0.15082"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Return Highest price - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest return price time sensor
    state = hass.states.get("sensor.easyenergy_today_energy_return_highest_price_time")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_return_highest_price_time"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_return_highest_price_time"
    assert state.state == "2026-04-19T18:00:00+00:00"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price - Return Time of highest price - today"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_today_energy_return")}
    assert device_entry.manufacturer == "easyEnergy"
    assert device_entry.name == "Energy market price - Return"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version

    # Return periods priced equal or higher sensor
    state = hass.states.get(
        "sensor.easyenergy_today_energy_return_hours_priced_equal_or_higher"
    )
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_return_hours_priced_equal_or_higher"
    )
    assert entry
    assert state
    assert (
        entry.unique_id
        == f"{entry_id}_today_energy_return_hours_priced_equal_or_higher"
    )
    assert state.state == "23"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy market price"
        " - Return Periods priced equal or higher than current - today"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes


@pytest.mark.freeze_time("2026-04-19 10:00:00+00:00")
async def test_gas_today(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the easyEnergy - Gas sensors."""
    entry_id = init_integration.entry_id

    # Current gas price sensor
    state = hass.states.get("sensor.easyenergy_today_gas_current_hour_price")
    entry = entity_registry.async_get("sensor.easyenergy_today_gas_current_hour_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_gas_current_hour_price"
    assert state.state == "0.6169"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Gas market price Current hour"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_today_gas")}
    assert device_entry.manufacturer == "easyEnergy"
    assert device_entry.name == "Gas market price"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


@pytest.mark.freeze_time("2026-04-19 13:00:00+00:00")
async def test_no_gas_today(
    hass: HomeAssistant, mock_easyenergy: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test the easyEnergy - No gas data available."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    mock_easyenergy.gas_prices.side_effect = EasyEnergyNoDataError

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.easyenergy_today_gas_current_hour_price"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.easyenergy_today_gas_current_hour_price")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.freeze_time("2026-04-19 00:00:00+00:00")
@pytest.mark.parametrize(
    ("minutes", "granularity"),
    [
        pytest.param(60, "hour", id="hourly"),
        pytest.param(15, "quarter", id="quarter-hourly"),
    ],
)
@pytest.mark.parametrize(
    ("sensor", "expected_state"),
    [
        pytest.param("usage_hours_priced_equal_or_lower", "3", id="usage"),
        pytest.param("return_hours_priced_equal_or_higher", "2", id="return"),
    ],
)
async def test_price_period_counts(
    hass: HomeAssistant,
    mock_easyenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
    minutes: int,
    granularity: str,
    sensor: str,
    expected_state: str,
) -> None:
    """Test inclusive counts for distinct usage and return prices at any interval size."""
    data = await async_load_json_object_fixture(hass, "today_energy.json", DOMAIN)
    start = dt_util.utcnow()
    interval = timedelta(minutes=minutes)
    prices = [
        {
            **data["prices"][0],
            "from": (start + index * interval).isoformat(),
            "until": (start + (index + 1) * interval).isoformat(),
            "granularity": granularity,
            "priceIncVat": usage_price,
            "invoicePrice": return_price,
        }
        for index, (usage_price, return_price) in enumerate(
            [(0.2, 0.3), (-0.1, 0.1), (0.2, 0.3), (0.4, 0.2)]
        )
    ]
    mock_easyenergy.energy_prices.return_value = Electricity.from_dict(
        prices, price_key="priceIncVat", return_price_key="invoicePrice"
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.easyenergy_today_energy_{sensor}")
    assert state
    assert state.state == expected_state
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_STATE_CLASS not in state.attributes
