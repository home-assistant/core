"""Tests for the sensors provided by the PVOutput integration."""
from homeassistant.components.pvoutput.const import DOMAIN
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
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the PVOutput sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.frenck_s_solar_farm_energy_consumed")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_energy_consumed")
    assert entry
    assert state
    assert entry.unique_id == "12345_energy_consumption"
    assert entry.entity_category is None
    assert state.state == "1000"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Frenck's Solar Farm Energy consumed"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_WATT_HOUR
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_energy_generated")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_energy_generated")
    assert entry
    assert state
    assert entry.unique_id == "12345_energy_generation"
    assert entry.entity_category is None
    assert state.state == "500"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Frenck's Solar Farm Energy generated"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_WATT_HOUR
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_efficiency")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_efficiency")
    assert entry
    assert state
    assert entry.unique_id == "12345_normalized_output"
    assert entry.entity_category is None
    assert state.state == "0.5"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's Solar Farm Efficiency"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == f"{ENERGY_KILO_WATT_HOUR}/{POWER_KILO_WATT}"
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_power_consumed")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_power_consumed")
    assert entry
    assert state
    assert entry.unique_id == "12345_power_consumption"
    assert entry.entity_category is None
    assert state.state == "2500"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's Solar Farm Power consumed"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_power_generated")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_power_generated")
    assert entry
    assert state
    assert entry.unique_id == "12345_power_generation"
    assert entry.entity_category is None
    assert state.state == "1500"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Frenck's Solar Farm Power generated"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_temperature")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_temperature")
    assert entry
    assert state
    assert entry.unique_id == "12345_temperature"
    assert entry.entity_category is None
    assert state.state == "20.2"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's Solar Farm Temperature"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.frenck_s_solar_farm_voltage")
    entry = entity_registry.async_get("sensor.frenck_s_solar_farm_voltage")
    assert entry
    assert state
    assert entry.unique_id == "12345_voltage"
    assert entry.entity_category is None
    assert state.state == "220.5"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's Solar Farm Voltage"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ELECTRIC_POTENTIAL_VOLT
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "12345")}
    assert device_entry.manufacturer == "PVOutput"
    assert device_entry.model == "Super Inverters Inc."
    assert device_entry.name == "Frenck's Solar Farm"
    assert device_entry.configuration_url == "https://pvoutput.org/list.jsp?sid=12345"
    assert device_entry.entry_type is None
    assert device_entry.sw_version is None
    assert device_entry.hw_version is None
