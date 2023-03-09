"""Tests for the sensors provided by the easyEnergy integration."""

from unittest.mock import MagicMock

from easyenergy import EasyEnergyNoDataError
import pytest

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
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

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_energy_usage_today(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the easyEnergy - Energy usage sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Current usage energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_usage_current_hour_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_usage_current_hour_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_usage_current_hour_price"
    assert state.state == "0.22541"
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
    assert state.state == "0.17665"
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
    assert state.state == "0.24677"
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
    assert state.state == "2023-01-19T16:00:00+00:00"
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


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_energy_return_today(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the easyEnergy - Energy return sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Current return energy price sensor
    state = hass.states.get("sensor.easyenergy_today_energy_return_current_hour_price")
    entry = entity_registry.async_get(
        "sensor.easyenergy_today_energy_return_current_hour_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_return_current_hour_price"
    assert state.state == "0.18629"
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
    assert state.state == "0.14599"
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
    assert state.state == "0.20394"
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
    assert state.state == "2023-01-19T16:00:00+00:00"
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


@pytest.mark.freeze_time("2023-01-19 10:00:00")
async def test_gas_today(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the easyEnergy - Gas sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Current gas price sensor
    state = hass.states.get("sensor.easyenergy_today_gas_current_hour_price")
    entry = entity_registry.async_get("sensor.easyenergy_today_gas_current_hour_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_gas_current_hour_price"
    assert state.state == "0.7253"
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


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_no_gas_today(
    hass: HomeAssistant, mock_easyenergy: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test the easyEnergy - No gas data available."""
    await async_setup_component(hass, "homeassistant", {})

    mock_easyenergy.gas_prices.side_effect = EasyEnergyNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.easyenergy_today_gas_current_hour_price"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.easyenergy_today_gas_current_hour_price")
    assert state
    assert state.state == STATE_UNKNOWN
