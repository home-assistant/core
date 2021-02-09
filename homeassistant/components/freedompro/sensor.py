"""Support for Freedompro sensors."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro sensors."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if (
            device["type"] == "temperatureSensor"
            or device["type"] == "humiditySensor"
            or device["type"] == "lightSensor"
        )
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity):
    """Representation of an Freedompro sensor."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._name = device["name"]
        self._uid = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._state = 0

    @property
    def name(self):
        """Return the name of the Freedompro sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = 0
        return support

    @property
    def device_class(self):
        """Define class to type of sensor."""
        if self._type == "temperatureSensor":
            return DEVICE_CLASS_TEMPERATURE
        if self._type == "humiditySensor":
            return DEVICE_CLASS_HUMIDITY
        if self._type == "lightSensor":
            return DEVICE_CLASS_ILLUMINANCE
        return DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
        """Return the status of the sensor."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "currentAmbientLightLevel" in state:
                    self._state = state["currentAmbientLightLevel"]
                if "currentRelativeHumidity" in state:
                    self._state = state["currentRelativeHumidity"]
                if "currentTemperature" in state:
                    self._state = state["currentTemperature"]
        return self._state
