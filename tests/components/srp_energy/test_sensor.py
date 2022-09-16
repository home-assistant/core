"""Tests for the srp_energy sensor platform."""
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.srp_energy import (
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SENSOR_NAME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.helpers import entity_registry as ent_reg

from . import ACCNT_ID


async def test_loading_sensors(hass, init_integration) -> None:
    """Test the srp energy sensors."""
    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][init_integration.entry_id]

    # Check sensors were loaded
    assert len(hass.states.async_all()) == 1


async def test_srp_entity(hass, init_integration):
    """Test the SrpEntity."""
    entity_registry = ent_reg.async_get(hass)

    assert "sensor.srp_energy_usage" in entity_registry.entities
    srp_entity = entity_registry.entities["sensor.srp_energy_usage"]

    assert srp_entity is not None
    assert srp_entity.original_name == f"{DEFAULT_NAME} {SENSOR_NAME}"
    assert srp_entity.unique_id == f"{ACCNT_ID}_energy_usage".lower()
    assert srp_entity.unit_of_measurement == ENERGY_KILO_WATT_HOUR
    assert srp_entity.original_icon == ICON
    assert srp_entity.original_device_class is SensorDeviceClass.ENERGY
    assert srp_entity.capabilities["state_class"] is SensorStateClass.TOTAL_INCREASING

    # assert srp_entity.available is not None

    usage_state = hass.states.get(srp_entity.entity_id)
    assert usage_state.state == "150.8"

    # Validate attributions
    assert (
        usage_state.attributes.get("state_class") is SensorStateClass.TOTAL_INCREASING
    )
    assert usage_state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert usage_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR

    assert usage_state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert usage_state.attributes.get(ATTR_ICON) == ICON
    assert (
        usage_state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{DEFAULT_NAME} {SENSOR_NAME}"
    )
