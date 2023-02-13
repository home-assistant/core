"""Tests for the Elgato sensor platform."""

import pytest

from homeassistant.components.elgato.const import DOMAIN
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
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light-mini"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration", "mock_elgato"),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Elgato sensors."""

    # Battery sensor
    state = hass.states.get("sensor.frenck_battery")
    assert state
    assert state.state == "78.57"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Battery"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_battery")
    assert entry
    assert entry.unique_id == "GW24L1A02987_battery"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {"sensor": {"suggested_display_precision": 0}}

    # Battery voltage sensor
    state = hass.states.get("sensor.frenck_battery_voltage")
    assert state
    assert state.state == "3.86"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Battery voltage"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_battery_voltage")
    assert entry
    assert entry.unique_id == "GW24L1A02987_voltage"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {
        "sensor": {"suggested_display_precision": 2},
        "sensor.private": {
            "suggested_unit_of_measurement": UnitOfElectricPotential.VOLT
        },
    }

    # Charging current sensor
    state = hass.states.get("sensor.frenck_charging_current")
    assert state
    assert state.state == "3.008"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Charging current"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricCurrent.AMPERE
    )
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_charging_current")
    assert entry
    assert entry.unique_id == "GW24L1A02987_input_charge_current"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {
        "sensor": {"suggested_display_precision": 2},
        "sensor.private": {
            "suggested_unit_of_measurement": UnitOfElectricCurrent.AMPERE
        },
    }

    # Charging power sensor
    state = hass.states.get("sensor.frenck_charging_power")
    assert state
    assert state.state == "12.66"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Charging power"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_charging_power")
    assert entry
    assert entry.unique_id == "GW24L1A02987_charge_power"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {"sensor": {"suggested_display_precision": 0}}

    # Charging voltage sensor
    state = hass.states.get("sensor.frenck_charging_voltage")
    assert state
    assert state.state == "4.208"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Charging voltage"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_charging_voltage")
    assert entry
    assert entry.unique_id == "GW24L1A02987_input_charge_voltage"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {
        "sensor": {"suggested_display_precision": 2},
        "sensor.private": {
            "suggested_unit_of_measurement": UnitOfElectricPotential.VOLT
        },
    }

    # Check if the entity is well registered in the device registry
    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "GW24L1A02987")}
    assert device_entry.manufacturer == "Elgato"
    assert device_entry.model == "Elgato Key Light Mini"
    assert device_entry.name == "Frenck"
    assert device_entry.sw_version == "1.0.4 (229)"
    assert device_entry.hw_version == "202"


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.frenck_battery_voltage",
        "sensor.frenck_charging_current",
        "sensor.frenck_charging_power",
        "sensor.frenck_charging_voltage",
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default Elgato sensors."""
    state = hass.states.get(entity_id)
    assert state is None

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
