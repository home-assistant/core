"""Support for Blink system camera sensors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN, TYPE_TEMPERATURE, TYPE_WIFI_STRENGTH

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    TYPE_TEMPERATURE: ["Temperature", TEMP_FAHRENHEIT, DEVICE_CLASS_TEMPERATURE],
    TYPE_WIFI_STRENGTH: [
        "Wifi Signal",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        DEVICE_CLASS_SIGNAL_STRENGTH,
    ],
}


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Blink sensor."""
    data = hass.data[DOMAIN][config.entry_id]
    entities = []
    for camera in data.cameras:
        for sensor_type in SENSORS:
            entities.append(BlinkSensor(data, camera, sensor_type))

    async_add_entities(entities)


class BlinkSensor(SensorEntity):
    """A Blink camera sensor."""

    def __init__(self, data, camera, sensor_type):
        """Initialize sensors from Blink camera."""
        name, units, device_class = SENSORS[sensor_type]
        self._attr_name = f"{DOMAIN} {camera} {name}"
        self._attr_device_class = device_class
        self.data = data
        self._camera = data.cameras[camera]
        self._attr_unit_of_measurement = units
        self._attr_unique_id = f"{self._camera.serial}-{sensor_type}"
        self._sensor_key = (
            "temperature_calibrated" if sensor_type == "temperature" else sensor_type
        )

    def update(self):
        """Retrieve sensor data from the camera."""
        self.data.refresh()
        try:
            self._attr_state = self._camera.attributes[self._sensor_key]
        except KeyError:
            self._attr_state = None
            _LOGGER.error(
                "%s not a valid camera attribute. Did the API change?", self._sensor_key
            )
