"""
Support for tracking the online status of a UPS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.apcupsd/
"""
from homeassistant.components import apcupsd
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = [apcupsd.DOMAIN]
DEFAULT_NAME = "UPS Online Status"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Instantiate an OnlineStatus binary sensor entity."""
    add_entities((OnlineStatus(config, apcupsd.DATA),))


class OnlineStatus(BinarySensorDevice):
    """Represent UPS online status."""

    def __init__(self, config, data):
        """Initialize the APCUPSd device."""
        self._config = config
        self._data = data
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the UPS online status sensor."""
        return self._config.get("name", DEFAULT_NAME)

    @property
    def is_on(self):
        """Return true if the UPS is online, else false."""
        return self._state == apcupsd.VALUE_ONLINE

    def update(self):
        """Get the status report from APCUPSd and set this entity's state."""
        self._state = self._data.status[apcupsd.KEY_STATUS]
