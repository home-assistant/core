"""Tests for the srp_energy sensor platform."""
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.srp_energy.const import ATTRIBUTION, DOMAIN, ICON
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant


async def test_loading_sensors(hass, init_integration) -> None:
    """Test the srp energy sensors."""
    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][init_integration.entry_id]

    # Check sensors were loaded
    assert len(hass.states.async_all()) == 1


async def test_srp_entity(hass, init_integration):
    """Test the SrpEntity."""
    usage_state = hass.states.get("sensor.energy_usage")
    assert usage_state.state == "150.8"

    # Validate attributions
    assert (
        usage_state.attributes.get("state_class") is SensorStateClass.TOTAL_INCREASING
    )
    assert usage_state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        usage_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    assert usage_state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert usage_state.attributes.get(ATTR_ICON) == ICON
