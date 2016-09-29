"""
Support for SleepIQ from SleepNumber.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sleepiq/
"""

import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle
from requests.exceptions import HTTPError

DOMAIN = 'sleepiq'

REQUIREMENTS = ['sleepyq==0.6']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

IS_IN_BED = 'is_in_bed'
SLEEP_NUMBER = 'sleep_number'
SENSOR_TYPES = {
    SLEEP_NUMBER: 'SleepNumber',
    IS_IN_BED: 'Is In Bed',
}

LEFT = 'left'
RIGHT = 'right'
SIDES = [LEFT, RIGHT]

_LOGGER = logging.getLogger(__name__)

DATA = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup SleepIQ.

    Will automatically load sensor components to support
    devices discovered on the account.
    """
    # pylint: disable=global-statement
    global DATA

    from sleepyq import Sleepyq
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    client = Sleepyq(username, password)
    try:
        DATA = SleepIQData(client)
        DATA.update()
    except HTTPError:
        message = """
            SleepIQ failed to login, double check your username and password"
        """
        _LOGGER.error(message)
        return False

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    return True


# pylint: disable=too-few-public-methods
class SleepIQData(object):
    """Gets the latest data from SleepIQ."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client
        self.beds = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""
        self._client.login()
        beds = self._client.beds_with_sleeper_status()

        self.beds = {bed.bed_id: bed for bed in beds}


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class SleepIQSensor(Entity):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        self._bed_id = bed_id
        self._side = side
        self.sleepiq_data = sleepiq_data
        self.side = None
        self.bed = None

        # added by subclass
        self._name = None
        self.type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'SleepNumber {} {} {}'.format(self.bed.name,
                                             self.side.sleeper.first_name,
                                             self._name)

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but thats fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update()

        self.bed = self.sleepiq_data.beds[self._bed_id]
        self.side = getattr(self.bed, self._side)
