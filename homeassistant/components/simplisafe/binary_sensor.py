"""Support for SimpliSafe binary sensors."""
from simplipy.entity import EntityTypes
from simplipy.websocket import EVENT_MOTION_DETECTED

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN

SUPPORTED_SENSOR_TYPES = [
    EntityTypes.motion,
    EntityTypes.entry,
    EntityTypes.carbon_monoxide,
    EntityTypes.smoke,
    EntityTypes.leak,
]

HA_SENSOR_TYPES = {
    EntityTypes.motion: DEVICE_CLASS_MOTION,
    EntityTypes.entry: DEVICE_CLASS_DOOR,
    EntityTypes.carbon_monoxide: DEVICE_CLASS_GAS,
    EntityTypes.smoke: DEVICE_CLASS_SMOKE,
    EntityTypes.leak: DEVICE_CLASS_MOISTURE,
}

SENSOR_MODELS = {
    EntityTypes.motion: "Motion Sensor",
    EntityTypes.entry: "Entry Sensor",
    EntityTypes.carbon_monoxide: "Carbon Monoxide Detector",
    EntityTypes.smoke: "Smoke Detector",
    EntityTypes.leak: "Water Sensor",
}

MOTION_SENSOR_TRIGGER_CLEAR = 10


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe binary sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            SimpliSafeBinarySensor(simplisafe, system, sensor)
            for system in simplisafe.systems.values()
            for sensor in system.sensors.values()
            if sensor.type in SUPPORTED_SENSOR_TYPES
        ]
    )

    async_add_entities(
        [
            SimpliSafeSensorBattery(simplisafe, system, sensor)
            for system in simplisafe.systems.values()
            for sensor in system.sensors.values()
            if sensor.type in SUPPORTED_SENSOR_TYPES
        ]
    )


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
    def unique_id(self):
        """Return unique ID of sensor."""
        return f"{self._sensor.serial}-sensor"

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

    @callback
    def async_update_from_websocket_event(self, event):
        """Update the entity with the provided websocket event data."""
        if (
            event.event_type == EVENT_MOTION_DETECTED
            and self.device_class == DEVICE_CLASS_MOTION
        ):
            self._is_on = True

            @callback
            def clear_delay_listener(now):
                """Clear motion sensor after delay."""
                self.is_on = False
                self.async_write_ha_state()

            async_call_later(
                self.hass, MOTION_SENSOR_TRIGGER_CLEAR, clear_delay_listener
            )


class SimpliSafeSensorBattery(SimpliSafeEntity, BinarySensorEntity):
    """Define a SimpliSafe battery binary sensor entity."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)
        self._system = system
        self._sensor = sensor
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
        """Return true if the battery is low."""
        return self._is_low

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_low = self._sensor.low_battery
