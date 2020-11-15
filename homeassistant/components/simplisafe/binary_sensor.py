"""Support for SimpliSafe binary sensors."""
from simplipy.entity import EntityTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback

from . import SimpliSafeBaseSensor
from .const import DATA_CLIENT, DOMAIN, LOGGER

SUPPORTED_BATTERY_SENSOR_TYPES = [
    EntityTypes.carbon_monoxide,
    EntityTypes.entry,
    EntityTypes.leak,
    EntityTypes.lock_keypad,
    EntityTypes.smoke,
    EntityTypes.temperature,
]

TRIGGERED_SENSOR_TYPES = {
    EntityTypes.carbon_monoxide: DEVICE_CLASS_GAS,
    EntityTypes.entry: DEVICE_CLASS_DOOR,
    EntityTypes.glass_break: DEVICE_CLASS_SAFETY,
    EntityTypes.leak: DEVICE_CLASS_MOISTURE,
    EntityTypes.motion: DEVICE_CLASS_MOTION,
    EntityTypes.smoke: DEVICE_CLASS_SMOKE,
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
            if sensor.type in TRIGGERED_SENSOR_TYPES:
                sensors.append(
                    TriggeredBinarySensor(
                        simplisafe,
                        system,
                        sensor,
                        TRIGGERED_SENSOR_TYPES[sensor.type],
                    )
                )
            if sensor.type in SUPPORTED_BATTERY_SENSOR_TYPES:
                sensors.append(BatteryBinarySensor(simplisafe, system, sensor))

    async_add_entities(sensors)


class TriggeredBinarySensor(SimpliSafeBaseSensor, BinarySensorEntity):
    """Define a binary sensor related to whether an entity has been triggered."""

    def __init__(self, simplisafe, system, sensor, device_class):
        """Initialize."""
        super().__init__(simplisafe, system, sensor)
        self._device_class = device_class
        self._is_on = False

    @property
    def device_class(self):
        """Return type of sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._is_on

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_on = self._sensor.triggered


class BatteryBinarySensor(SimpliSafeBaseSensor, BinarySensorEntity):
    """Define a SimpliSafe battery binary sensor entity."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor)
        self._is_low = False

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
