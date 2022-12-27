"""Tests for the sensors provided by the P1 Monitor integration."""
from unittest.mock import MagicMock

from p1monitor import P1MonitorNoDataError
import pytest

from homeassistant.components.p1_monitor.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CURRENCY_EURO,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_smartmeter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the P1 Monitor - SmartMeter sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.smartmeter_power_consumption")
    entry = entity_registry.async_get("sensor.smartmeter_power_consumption")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_smartmeter_power_consumption"
    assert state.state == "877"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Power Consumption"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.smartmeter_energy_consumption_high")
    entry = entity_registry.async_get("sensor.smartmeter_energy_consumption_high")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_smartmeter_energy_consumption_high"
    assert state.state == "2770.133"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Consumption - High Tariff"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.smartmeter_energy_tariff_period")
    entry = entity_registry.async_get("sensor.smartmeter_energy_tariff_period")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_smartmeter_energy_tariff_period"
    assert state.state == "high"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Tariff Period"
    assert state.attributes.get(ATTR_ICON) == "mdi:calendar-clock"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_smartmeter")}
    assert device_entry.manufacturer == "P1 Monitor"
    assert device_entry.name == "SmartMeter"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_phases(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the P1 Monitor - Phases sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.phases_voltage_phase_l1")
    entry = entity_registry.async_get("sensor.phases_voltage_phase_l1")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_phases_voltage_phase_l1"
    assert state.state == "233.6"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Voltage Phase L1"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ELECTRIC_POTENTIAL_VOLT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.phases_current_phase_l1")
    entry = entity_registry.async_get("sensor.phases_current_phase_l1")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_phases_current_phase_l1"
    assert state.state == "1.6"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Current Phase L1"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ELECTRIC_CURRENT_AMPERE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.phases_power_consumed_phase_l1")
    entry = entity_registry.async_get("sensor.phases_power_consumed_phase_l1")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_phases_power_consumed_phase_l1"
    assert state.state == "315"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Power Consumed Phase L1"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_phases")}
    assert device_entry.manufacturer == "P1 Monitor"
    assert device_entry.name == "Phases"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_settings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the P1 Monitor - Settings sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.settings_energy_consumption_price_low")
    entry = entity_registry.async_get("sensor.settings_energy_consumption_price_low")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_settings_energy_consumption_price_low"
    assert state.state == "0.20522"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Consumption Price - Low"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}"
    )

    state = hass.states.get("sensor.settings_energy_production_price_low")
    entry = entity_registry.async_get("sensor.settings_energy_production_price_low")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_settings_energy_production_price_low"
    assert state.state == "0.20522"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Production Price - Low"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}"
    )

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_settings")}
    assert device_entry.manufacturer == "P1 Monitor"
    assert device_entry.name == "Settings"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_watermeter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the P1 Monitor - WaterMeter sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    state = hass.states.get("sensor.watermeter_consumption_day")
    entry = entity_registry.async_get("sensor.watermeter_consumption_day")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_watermeter_consumption_day"
    assert state.state == "112.0"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Consumption Day"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_LITERS

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_watermeter")}
    assert device_entry.manufacturer == "P1 Monitor"
    assert device_entry.name == "WaterMeter"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_no_watermeter(
    hass: HomeAssistant, mock_p1monitor: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the P1 Monitor - Without WaterMeter sensors."""
    mock_p1monitor.watermeter.side_effect = P1MonitorNoDataError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.states.get("sensor.watermeter_consumption_day")
    assert not hass.states.get("sensor.consumption_total")
    assert not hass.states.get("sensor.pulse_count")


@pytest.mark.parametrize(
    "entity_id",
    ("sensor.smartmeter_gas_consumption",),
)
async def test_smartmeter_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test the P1 Monitor - SmartMeter sensors that are disabled by default."""
    entity_registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
