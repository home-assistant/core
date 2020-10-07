"""Support for SimpliSafe binary sensors."""
from simplipy.entity import EntityTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback

from . import SENSOR_MODELS, SimpliSafeEntity, SimpliSafeSensorBattery
from .const import DATA_CLIENT, DOMAIN

SUPPORTED_SENSOR_TYPES = [
    EntityTypes.entry,
    EntityTypes.carbon_monoxide,
    EntityTypes.smoke,
    EntityTypes.leak,
]

HA_SENSOR_TYPES = {
    EntityTypes.entry: DEVICE_CLASS_DOOR,
    EntityTypes.carbon_monoxide: DEVICE_CLASS_GAS,
    EntityTypes.smoke: DEVICE_CLASS_SMOKE,
    EntityTypes.leak: DEVICE_CLASS_MOISTURE,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe binary sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    # Add sensor
    sensors = [
        SimpliSafeBinarySensor(simplisafe, system, sensor)
        for system in simplisafe.systems.values()
        for sensor in system.sensors.values()
        if sensor.type in SUPPORTED_SENSOR_TYPES
    ]

    # Add low battery status entity for every sensor
    battery_sensors = [
        SimpliSafeSensorBattery(simplisafe, system, sensor)
        for system in simplisafe.systems.values()
        for sensor in system.sensors.values()
        if sensor.type in SUPPORTED_SENSOR_TYPES
    ]

    async_add_entities(sensors + battery_sensors)


class SimpliSafeBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a SimpliSafe binary sensor entity."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)
        self._system = system
        self._sensor = sensor
        self._is_on = False

    @property
    def device_class(self):
        """Return type of sensor."""
        return HA_SENSOR_TYPES[self._sensor.type]

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._sensor.serial)},
            "manufacturer": "SimpliSafe",
            "model": SENSOR_MODELS[self._sensor.type],
            "name": self._sensor.name,
            "via_device": (DOMAIN, self._system.serial),
        }

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._is_on

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_on = self._sensor.triggered
