"""Support for Myfitnesspal totals as sensors."""
import logging
from datetime import date

import myfitnesspal
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

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
    try:
        client = myfitnesspal.Client(
            CONF_USERNAME, CONF_PASSWORD)

        _LOGGER.debug('Connected to mfp')

    except Exception as err:
        _LOGGER.error("mfp error %s", err)
        return

    add_devices([MyFitnessPalSensor(client)])


class MyFitnessPalSensor(Entity):
    """Representation of a Sensor."""

    ICON = 'mdi:barley'

    def __init__(self, client):
        """Initialize the sensor."""
        self._attributes = {}
        self._state = None

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
        
        startdate = date.today()
        print(client)
        mfpday = client.get_date(
            startdate.year, startdate.month, startdate.day)
        print(mfpday)
        totals = mfpday.totals
        print(totals)

        if 'calories' in totals:
            self._state = totals['calories']
            totals.pop('calories')
            self._attributes = totals
        elif totals == {}:
            return 0
