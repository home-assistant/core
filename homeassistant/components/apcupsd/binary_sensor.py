"""Support for tracking the online status of a UPS."""
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, KEY_STATUS, VALUE_ONLINE

DEFAULT_NAME = "UPS Online Status"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an APCUPSd Online Status binary sensor."""
    apcups_data = hass.data[DOMAIN]

    add_entities([OnlineStatus(config, apcups_data)], True)


class OnlineStatus(BinarySensorDevice):
    """Representation of an UPS online status."""

    def __init__(self, config, data):
        """Initialize the APCUPSd binary device."""
        self._config = config
        self._data = data
        self._state = None

    @property
    def name(self):
        """Return the name of the UPS online status sensor."""
        return self._config[CONF_NAME]

    @property
    def is_on(self):
        """Return true if the UPS is online, else false."""
        return self._state & VALUE_ONLINE > 0

    def update(self):
        """Get the status report from APCUPSd and set this entity's state."""
        self._state = int(self._data.status[KEY_STATUS], 16)
