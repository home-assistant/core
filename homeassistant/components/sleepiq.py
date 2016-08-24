"""
Support for SleepIQ from SleepNumber

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sleepiq/
"""

import logging
from datetime import timedelta

from homeassistant.helpers import discovery
from homeassistant.util import Throttle

from sleepyq import Sleepyq

DOMAIN = 'sleepiq'

REQUIREMENTS = ['sleepyq==0.5']

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SENSOR_TYPES = {
    'sleep_number': 'SleepNumber',
    'is_in_bed': 'Is In Bed',
}

ICON = 'mdi:hotel'

class SleepIQData(object):
    """Gets the latest data from SleepIQ."""

    def __init__(self, login, password):
        """Initialize the data object."""
        self._client = Sleepyq(login, password)
        self.sides = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""

        self._client.login()
        beds = self._client.beds()
        sleepers = self._client.sleepers()
        family_statuses = self._client.bed_family_status()

        sleepers_by_id = {sleeper['sleeperId']: sleeper for sleeper in sleepers}
        bed_family_statuses_by_bed_id = {family_status['bedId']: family_status for family_status in family_statuses}

        # FIXME handle 0 and > 1 bed
        bed = beds[0]

        self.bed_name = bed['name']

        family_status = bed_family_statuses_by_bed_id[bed['bedId']]

        for side in ['left', 'right']:
            from IPython import embed
            embed()
            sleeper_key = 'sleeper' + side.title() + 'Id'
            sleeper = sleepers_by_id[bed[sleeper_key]]
            status_key = side + 'Side'
            status = family_status[status_key]

            self.sides[side] = {
                'sleeper': sleeper['firstName'],
                'is_in_bed': status['isInBed'],
                'sleep_number': status['sleepNumber'],
            }

def setup(hass, config):
    """Setup SleepIQ.

    Will automatically load sensor components to support
    devices discovered on the account.
    """
    # pylint: disable=global-statement, import-error
    global DATA

    DATA = SleepIQData(config[DOMAIN]['login'], config[DOMAIN]['password'])
    DATA.update()

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    return True
