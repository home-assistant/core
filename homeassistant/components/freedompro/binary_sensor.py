"""Support for Freedompro binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro binary sensors."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if (
            device["type"] == "smokeSensor"
            or device["type"] == "occupancySensor"
            or device["type"] == "motionSensor"
            or device["type"] == "contactSensor"
        )
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, BinarySensorEntity):
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
        self._on = False

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
        if self._type == "smokeSensor":
            return DEVICE_CLASS_SMOKE
        if self._type == "occupancySensor":
            return DEVICE_CLASS_OCCUPANCY
        if self._type == "motionSensor":
            return DEVICE_CLASS_MOTION
        if self._type == "contactSensor":
            return DEVICE_CLASS_OPENING
        return DEVICE_CLASS_OPENING

    @property
    def is_on(self):
        """Return the status of the sensor."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "contactSensorState" in state:
                    self._on = state["contactSensorState"]
                if "motionDetected" in state:
                    self._on = state["motionDetected"]
                if "occupancyDetected" in state:
                    self._on = state["occupancyDetected"]
                if "smokeDetected" in state:
                    self._on = state["smokeDetected"]
        return self._on
