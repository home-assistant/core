"""Setup Mullvad VPN sensors."""
from homeassistant.helpers.entity import Entity

from . import get_coordinator
from .const import DOMAIN

SENSORS = (
    "ip",
    "country",
    "city",
    "longitude",
    "latitude",
    "mullvad_exit_ip_hostname",
    "mullvad_server_type",
    "blacklisted",
    "organization",
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        MullvadSensor(coordinator, sensor_name) for sensor_name in SENSORS
    )


class MullvadSensor(Entity):
    """Represents a Mullvad sensor."""

    def __init__(self, coordinator, name):
        """Initialize the Mullvad sensor."""
        self.coordinator = coordinator
        self._name = name
        self._state_attributes = None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:vpn"

    @property
    def name(self):
        """Return the name for this sensor."""
        if self._name.startswith(DOMAIN):
            return self._name.replace("_", " ").title()
        return f"{DOMAIN}_{self._name}".replace("_", " ").title()

    @property
    def state(self):
        """Return the state for this sensor."""
        # Handle blacklisted differently
        if self._name == "blacklisted":
            self._state_attributes = self.coordinator.data[self._name]
            return self.coordinator.data[self._name]["blacklisted"]
        else:
            return self.coordinator.data[self._name]

    @property
    def state_attributes(self):
        """Return the state attributes for this sensor."""
        return self._state_attributes
