"""Setup Mullvad VPN Binary Sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

BINARY_SENSORS = (
    {
        CONF_ID: "mullvad_exit_ip",
        CONF_NAME: "Mullvad Exit IP",
        CONF_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
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

    def __init__(self, coordinator, sensor):
        """Initialize the Mullvad binary sensor."""
        super().__init__(coordinator)
        self.id = sensor[CONF_ID]
        self._name = sensor[CONF_NAME]
        self._device_class = sensor[CONF_DEVICE_CLASS]

    @property
    def device_class(self):
        """Return the device class for this binary sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name for this binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state for this binary sensor."""
        return self.coordinator.data[self.id]
