"""Setup Mullvad VPN Binary Sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

BINARY_SENSORS = (
    {
        "id": "mullvad_exit_ip",
        "name": "Mullvad Exit IP",
        "device_class": DEVICE_CLASS_CONNECTIVITY,
    },
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN]

    async_add_entities(
        MullvadBinarySensor(coordinator, sensor) for sensor in BINARY_SENSORS
    )


class MullvadBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represents a Mullvad binary sensor."""

    def __init__(self, coordinator, sensor):  # pylint: disable=super-init-not-called
        """Initialize the Mullvad binary sensor."""
        self.coordinator = coordinator
        self.id = sensor["id"]
        self._name = sensor["name"]

    @property
    def device_class(self):
        """Return the device class for this binary sensor."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def icon(self):
        """Return the icon for this binary sensor."""
        return "mdi:vpn"

    @property
    def name(self):
        """Return the name for this binary sensor."""
        return self._name

    @property
    def state(self):
        """Return the state for this binary sensor."""
        return self.coordinator.data[self.id]
