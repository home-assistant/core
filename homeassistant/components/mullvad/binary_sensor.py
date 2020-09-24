"""Setup Mullvad VPN Binary Sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from . import get_coordinator
from .const import DOMAIN

BINARY_SENSORS = ("mullvad_exit_ip",)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        MullvadBinarySensor(coordinator, sensor_name) for sensor_name in BINARY_SENSORS
    )


class MullvadBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represents a Mullvad binary sensor."""

    def __init__(self, coordinator, name):
        """Initialize the Mullvad binary sensor."""
        self.coordinator = coordinator
        self._name = name

    @property
    def icon(self):
        """Return the icon for this binary sensor."""
        return "mdi:vpn"

    @property
    def name(self):
        """Return the name for this binary sensor."""
        if self._name.startswith(DOMAIN):
            return self._name.replace("_", " ").title()
        return f"{DOMAIN}_{self._name}".replace("_", " ").title()

    @property
    def state(self):
        """Return the state for this binary sensor."""
        return self.coordinator.data[self._name]
