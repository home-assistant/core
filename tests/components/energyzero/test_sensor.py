"""Tests for the sensors provided by the EnergyZero integration."""

from unittest.mock import MagicMock

from energyzero import EnergyZeroNoDataError
import pytest

from homeassistant.components.energyzero.const import DOMAIN
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


@pytest.mark.freeze_time("2022-12-07 15:00:00")
async def test_energy_today(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the EnergyZero - Energy sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Current energy price sensor
    state = hass.states.get("sensor.energyzero_today_energy_current_hour_price")
    entry = entity_registry.async_get(
        "sensor.energyzero_today_energy_current_hour_price"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_current_hour_price"
    assert state.state == "0.49"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy market price Current hour"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Average price sensor
    state = hass.states.get("sensor.energyzero_today_energy_average_price")
    entry = entity_registry.async_get("sensor.energyzero_today_energy_average_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_average_price"
    assert state.state == "0.37"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price Average - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest price sensor
    state = hass.states.get("sensor.energyzero_today_energy_max_price")
    entry = entity_registry.async_get("sensor.energyzero_today_energy_max_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_max_price"
    assert state.state == "0.55"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price Highest price - today"
    )
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    # Highest price time sensor
    state = hass.states.get("sensor.energyzero_today_energy_highest_price_time")
    entry = entity_registry.async_get(
        "sensor.energyzero_today_energy_highest_price_time"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_energy_highest_price_time"
    assert state.state == "2022-12-07T16:00:00+00:00"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Energy market price Time of highest price - today"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_today_energy")}
    assert device_entry.manufacturer == "EnergyZero"
    assert device_entry.name == "Energy market price"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


@pytest.mark.freeze_time("2022-12-07 15:00:00")
async def test_gas_today(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the EnergyZero - Gas sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Current gas price sensor
    state = hass.states.get("sensor.energyzero_today_gas_current_hour_price")
    entry = entity_registry.async_get("sensor.energyzero_today_gas_current_hour_price")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_today_gas_current_hour_price"
    assert state.state == "1.47"
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
    assert device_entry.manufacturer == "EnergyZero"
    assert device_entry.name == "Gas market price"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


@pytest.mark.freeze_time("2022-12-07 15:00:00")
async def test_no_gas_today(
    hass: HomeAssistant, mock_energyzero: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test the EnergyZero - No gas sensors available."""
    await async_setup_component(hass, "homeassistant", {})

    mock_energyzero.gas_prices.side_effect = EnergyZeroNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.energyzero_today_gas_current_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energyzero_today_gas_current_hour_price")
    assert state
    assert state.state == STATE_UNKNOWN
