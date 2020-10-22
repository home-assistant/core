"""Support for SimpliSafe binary sensors."""
from simplipy.entity import EntityTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN, LOGGER

SUPPORTED_BATTERY_SENSOR_TYPES = [
    EntityTypes.carbon_monoxide,
    EntityTypes.entry,
    EntityTypes.leak,
    EntityTypes.lock,
    EntityTypes.smoke,
    EntityTypes.temperature,
]

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

SENSOR_MODELS = {
    EntityTypes.entry: "Entry Sensor",
    EntityTypes.carbon_monoxide: "Carbon Monoxide Detector",
    EntityTypes.smoke: "Smoke Detector",
    EntityTypes.leak: "Water Sensor",
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe binary sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    sensors = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type in SUPPORTED_SENSOR_TYPES:
                sensors.append(SimpliSafeBinarySensor(simplisafe, system, sensor))
            if sensor.type in SUPPORTED_BATTERY_SENSOR_TYPES:
                sensors.append(SimpliSafeSensorBattery(simplisafe, system, sensor))

    async_add_entities(sensors)


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
        info = super().device_info
        info["identifiers"] = {(DOMAIN, self._sensor.serial)}
        info["model"] = SENSOR_MODELS[self._sensor.type]
        info["name"] = self._sensor.name
        return info

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._is_on

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_on = self._sensor.triggered


class SimpliSafeSensorBattery(SimpliSafeEntity, BinarySensorEntity):
    """Define a SimpliSafe battery binary sensor entity."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)
        self._sensor = sensor
        self._is_low = False

        self._device_info["identifiers"] = {(DOMAIN, sensor.serial)}
        self._device_info["model"] = SENSOR_MODELS[sensor.type]
        self._device_info["name"] = sensor.name

    @property
    def device_class(self):
        """Return type of sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unique_id(self):
        """Return unique ID of sensor."""
        return f"{self._sensor.serial}-battery"

    @property
    def is_on(self):
        """Return true if the battery is low."""
        return self._is_low

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_low = self._sensor.low_battery
