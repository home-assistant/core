"""Support for Taps Affs."""
from datetime import timedelta
import logging

from tapsaff import TapsAff
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION = "location"

DEFAULT_NAME = "Taps Aff"

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LOCATION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Taps Aff binary sensor."""
    name = config.get(CONF_NAME)
    location = config.get(CONF_LOCATION)

    taps_aff_data = TapsAffData(location)

    add_entities([TapsAffSensor(taps_aff_data, name)], True)


class TapsAffSensor(BinarySensorEntity):
    """Implementation of a Taps Aff binary sensor."""

    def __init__(self, taps_aff_data, name):
        """Initialize the Taps Aff sensor."""
        self.data = taps_aff_data
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def is_on(self):
        """Return true if taps aff."""
        return self.data.is_taps_aff

    def update(self):
        """Get the latest data."""
        self.data.update()


class TapsAffData:
    """Class for handling the data retrieval for pins."""

    def __init__(self, location):
        """Initialize the data object."""

        self._is_taps_aff = None
        self.taps_aff = TapsAff(location)

    @property
    def is_taps_aff(self):
        """Return true if taps aff."""
        return self._is_taps_aff

    def update(self):
        """Get the latest data from the Taps Aff API and updates the states."""
        try:
            self._is_taps_aff = self.taps_aff.is_taps_aff
        except RuntimeError:
            _LOGGER.error("Update failed. Check configured location")
