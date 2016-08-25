"""
Support for SleepIQ from SleepNumber

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sleepiq/
"""

import logging
from datetime import timedelta

from homeassistant.helpers import validate_config, discovery
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle

from sleepyq import Sleepyq

DOMAIN = 'sleepiq'

REQUIREMENTS = ['sleepyq==0.6']

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

ICON = 'mdi:hotel'

IS_IN_BED = 'is_in_bed'
SLEEP_NUMBER = 'sleep_number'
SENSOR_TYPES = {
    SLEEP_NUMBER: 'SleepNumber',
    IS_IN_BED: 'Is In Bed',
}

LEFT = 'left'
RIGHT = 'right'
SIDES = [LEFT, RIGHT]

class SleepIQData(object):
    """Gets the latest data from SleepIQ."""

    def __init__(self, login, password):
        """Initialize the data object."""
        self._client = Sleepyq(login, password)
        self.beds = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""

        self._client.login()
        beds = self._client.beds_with_sleeper_status()

        self.beds = {bed.bed_id: bed for bed in beds}

def setup(hass, config):
    """Setup SleepIQ.

    Will automatically load sensor components to support
    devices discovered on the account.
    """
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]}, logger):
        return False

    # pylint: disable=global-statement, import-error
    global DATA

    DATA = SleepIQData(config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD])
    DATA.update()

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    return True
