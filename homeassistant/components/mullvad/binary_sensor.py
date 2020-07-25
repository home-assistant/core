"""Setup Mullvad Binary Sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import BINARY_SENSORS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Mullvad binary sensors."""
    if discovery_info is None:
        return
    binary_sensors = []
    for name in hass.data[DOMAIN]:
        if name in BINARY_SENSORS:
            binary_sensors.append(MullvadBinarySensor(name, hass.data[DOMAIN][name]))
    add_entities(binary_sensors, True)


class MullvadBinarySensor(BinarySensorEntity):
    """Represents a Mullvad binary sensor."""

    def __init__(self, name, state):
        """Initialize the Mullvad binary sensor."""
        self._name = name
        self._state = state

    @property
    def icon(self):
        """Return the icon for this binary sensor."""
        return "mdi:vpn"

    @property
    def name(self):
        """Return the name for this binary sensor."""
        if self._name.startswith(DOMAIN):
            return self._name.replace("_", " ").title()
        else:
            return f"{DOMAIN}_{self._name}".replace("_", " ").title()

    @property
    def state(self):
        """Return the state for this binary sensor."""
        return self._state

    def update(self):
        """Update the binary sensor."""
        self._state = self.hass.data[DOMAIN][self._name]
