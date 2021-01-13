"""Binary Sensor platform for Unifi Video integration."""

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up Unifi Video sensor platform."""

    coordinator = hass.data[DOMAIN]["coordinator"]
    identifier = hass.data[DOMAIN]["camera_id_field"]

    async_add_devices(
        [
            UnifiVideoCameraConnectionSensor(
                coordinator,
                coordinator.data[camera][identifier],
                coordinator.data[camera]["name"],
            )
            for camera in coordinator.data
        ],
        True,
    )
    return True


class UnifiVideoCameraConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Camera connection Status."""

    def __init__(self, coordinator, uuid, name):
        """Initialize an Unifi camera connection status sensor."""
        super().__init__(coordinator)
        self._uuid = uuid
        self._name = name

    @property
    def name(self):
        """Return the name."""
        return "%s Connection Status" % self._name

    @property
    def unique_id(self):
        """Return a unique id."""
        return "%s-connection-status" % self._uuid

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def is_on(self):
        """Return if filter needs cleaning."""
        return self.coordinator.data[self._uuid]["state"] == "CONNECTED"
