"""Tests for the sensors provided by the Pure Energie integration."""

from homeassistant.components.pure_energie.const import DOMAIN
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
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Pure Energie - SmartBridge sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.pem_energy_consumption_total")
    entry = entity_registry.async_get("sensor.pem_energy_consumption_total")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_energy_consumption_total"
    assert state.state == "17762.1"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Consumption"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.pem_energy_production_total")
    entry = entity_registry.async_get("sensor.pem_energy_production_total")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_energy_production_total"
    assert state.state == "21214.6"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Production"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.pem_power_flow")
    entry = entity_registry.async_get("sensor.pem_power_flow")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_power_flow"
    assert state.state == "338"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Power Flow"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "aabbccddeeff")}
    assert device_entry.name == "home"
    assert device_entry.manufacturer == "NET2GRID"
    assert device_entry.model == "SBWF3102"
    assert device_entry.sw_version == "1.6.16"
