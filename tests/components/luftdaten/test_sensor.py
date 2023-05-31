"""Tests for the sensors provided by the Luftdaten integration."""
from homeassistant.components.luftdaten.const import DOMAIN
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
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_luftdaten_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Luftdaten sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry = entity_registry.async_get("sensor.sensor_12345_temperature")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_temperature"

    state = hass.states.get("sensor.sensor_12345_temperature")
    assert state
    assert state.state == "22.3"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 Temperature"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("sensor.sensor_12345_humidity")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_humidity"

    state = hass.states.get("sensor.sensor_12345_humidity")
    assert state
    assert state.state == "34.7"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 Humidity"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("sensor.sensor_12345_pressure")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_pressure"

    state = hass.states.get("sensor.sensor_12345_pressure")
    assert state
    assert state.state == "98545.0"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 Pressure"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.PA
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("sensor.sensor_12345_pressure_at_sealevel")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_pressure_at_sealevel"

    state = hass.states.get("sensor.sensor_12345_pressure_at_sealevel")
    assert state
    assert state.state == "103102.13"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 Pressure at sealevel"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.PA
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("sensor.sensor_12345_pm10")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_P1"

    state = hass.states.get("sensor.sensor_12345_pm10")
    assert state
    assert state.state == "8.5"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 PM10"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("sensor.sensor_12345_pm2_5")
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345_P2"

    state = hass.states.get("sensor.sensor_12345_pm2_5")
    assert state
    assert state.state == "4.07"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sensor 12345 PM2.5"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "12345")}
    assert device_entry.manufacturer == "Sensor.Community"
    assert device_entry.name == "Sensor 12345"
    assert (
        device_entry.configuration_url
        == "https://devices.sensor.community/sensors/12345/settings"
    )
