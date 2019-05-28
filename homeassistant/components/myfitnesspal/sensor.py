"""Support for Myfitnesspal totals as sensors."""
from datetime import date

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

DOMAIN = 'myfitnesspal'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

ENERGY_KILOCALORIES = 'kcal'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set the sensor platform."""
    add_devices([MyFitnessPalSensor(config)])


class MyFitnessPalSensor(Entity):
    """Representation of a Sensor."""

    ICON = 'mdi:barley'

    def __init__(self, config):
        """Initialize the sensor."""
        self._attributes = {}
        self._state = None
        self._username = config['username']
        self._password = config['password']

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'myfitnesspal totals'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILOCALORIES

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        import myfitnesspal
        client = myfitnesspal.Client(self._username, self._password)

        startdate = date.today()
        mfpday = client.get_date(
            startdate.year, startdate.month, startdate.day)
        totals = mfpday.totals
        if 'calories' in totals:
            self._state = totals['calories']
            totals.pop('calories')
            self._attributes = totals
