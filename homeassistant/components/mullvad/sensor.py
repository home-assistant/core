"""Setup Mullvad sensors."""
import logging

from homeassistant.helpers.entity import Entity

from . import DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Mullvad sensors."""
    if discovery_info is None:
        return
    sensors = []
    for name in hass.data[DOMAIN]:
        if name in SENSORS:
            sensors.append(MullvadSensor(name, hass.data[DOMAIN][name]))
    add_entities(sensors, True)


class MullvadSensor(Entity):
    """Represents a Mullvad sensor."""

    def __init__(self, name, state):
        """Initialize the Mullvad sensor."""
        self._name = name
        self._state = state
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
        else:
            return f"{DOMAIN}_{self._name}".replace("_", " ").title()

    @property
    def state(self):
        """Return the state for this sensor."""
        # Handle blacklisted differently
        if self._name == "blacklisted":
            self._state_attributes = self._state
            return self._state["blacklisted"]
        else:
            return self._state

    @property
    def state_attributes(self):
        """Return the state attributes for this sensor."""
        return self._state_attributes

    def update(self):
        """Update the sensor."""
        self._state = self.hass.data[DOMAIN][self._name]
