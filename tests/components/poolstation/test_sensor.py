"""Tests for the Poolstation sensor platform."""
from homeassistant.components.poolstation.sensor import (
    ELECTROLYSIS_SUFFIX,
    PH_SUFFIX,
    SALT_SUFFIX,
    TEMPERATURE_SUFFIX,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .common import init_integration, mock_config_entry, mock_pool


async def test_pool_sensors(hass: HomeAssistant) -> None:
    """Test the creation and values of the Poolstation sensors."""
    config_entry = mock_config_entry(uniqe_id="id_my_pool_sensor_test_pool")
    pool = mock_pool(id=123, alias="my_pool")
    await init_integration(hass, config_entry, [pool])
    registry = entity_registry.async_get(hass)

    # PH
    state = hass.states.get("sensor.my_pool_ph")
    assert state
    assert state.state == str(pool.current_ph)
    assert state.attributes.get(ATTR_ICON) == "mdi:ph"
    entry = registry.async_get("sensor.my_pool_ph")
    assert entry
    assert entry.unique_id == f"{pool.id}{PH_SUFFIX}"

    # Temperature
    state = hass.states.get("sensor.my_pool_temperature")
    assert state
    assert state.state == str(pool.temperature)
    assert state.attributes.get(ATTR_ICON) == "mdi:coolant-temperature"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    entry = registry.async_get("sensor.my_pool_temperature")
    assert entry
    assert entry.unique_id == f"{pool.id}{TEMPERATURE_SUFFIX}"

    # Salt concentration
    state = hass.states.get("sensor.my_pool_salt_concentration")
    assert state
    assert state.state == str(pool.salt_concentration)
    assert state.attributes.get(ATTR_ICON) == "mdi:shaker"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "gr/l"
    entry = registry.async_get("sensor.my_pool_salt_concentration")
    assert entry
    assert entry.unique_id == f"{pool.id}{SALT_SUFFIX}"

    # Electrolysis
    state = hass.states.get("sensor.my_pool_electrolysis")
    assert state
    assert state.state == str(pool.percentage_electrolysis)
    assert state.attributes.get(ATTR_ICON) == "mdi:water-percent"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    entry = registry.async_get("sensor.my_pool_electrolysis")
    assert entry
    assert entry.unique_id == f"{pool.id}{ELECTROLYSIS_SUFFIX}"
