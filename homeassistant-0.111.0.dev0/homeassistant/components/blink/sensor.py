"""Support for Blink system camera sensors."""
import logging

from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, TYPE_BATTERY, TYPE_TEMPERATURE, TYPE_WIFI_STRENGTH

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    TYPE_TEMPERATURE: ["Temperature", TEMP_FAHRENHEIT, "mdi:thermometer"],
    TYPE_BATTERY: ["Battery", "", "mdi:battery-80"],
    TYPE_WIFI_STRENGTH: ["Wifi Signal", "dBm", "mdi:wifi-strength-2"],
}


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Blink sensor."""
    data = hass.data[DOMAIN][config.entry_id]
    entities = []
    for camera in data.cameras:
        for sensor_type in SENSORS:
            entities.append(BlinkSensor(data, camera, sensor_type))

    async_add_entities(entities)


class BlinkSensor(Entity):
    """A Blink camera sensor."""

    def __init__(self, data, camera, sensor_type):
        """Initialize sensors from Blink camera."""
        name, units, icon = SENSORS[sensor_type]
        self._name = f"{DOMAIN} {camera} {name}"
        self._camera_name = name
        self._type = sensor_type
        self.data = data
        self._camera = data.cameras[camera]
        self._state = None
        self._unit_of_measurement = units
        self._icon = icon
        self._unique_id = f"{self._camera.serial}-{self._type}"
        self._sensor_key = self._type
        if self._type == "temperature":
            self._sensor_key = "temperature_calibrated"

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id for the camera sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the camera's current state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Retrieve sensor data from the camera."""
        self.data.refresh()
        try:
            self._state = self._camera.attributes[self._sensor_key]
        except KeyError:
            self._state = None
            _LOGGER.error(
                "%s not a valid camera attribute. Did the API change?", self._sensor_key
            )
