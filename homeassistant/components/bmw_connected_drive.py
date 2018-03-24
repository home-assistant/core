"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/bmw_connected_drive/
"""
import datetime
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import discovery
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['bimmer_connected==0.5.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'bmw_connected_drive'
CONF_REGION = 'region'


ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_REGION): vol.Any('north_america', 'china',
                                       'rest_of_world'),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: ACCOUNT_SCHEMA
    },
}, extra=vol.ALLOW_EXTRA)


BMW_COMPONENTS = ['binary_sensor', 'device_tracker', 'lock', 'sensor']
UPDATE_INTERVAL = 5  # in minutes


def setup(hass, config):
    """Set up the BMW connected drive components."""
    accounts = []
    for name, account_config in config[DOMAIN].items():
        username = account_config[CONF_USERNAME]
        password = account_config[CONF_PASSWORD]
        region = account_config[CONF_REGION]
        _LOGGER.debug('Adding new account %s', name)
        bimmer = BMWConnectedDriveAccount(username, password, region, name)
        accounts.append(bimmer)

        # update every UPDATE_INTERVAL minutes, starting now
        # this should even out the load on the servers

        now = datetime.datetime.now()
        track_utc_time_change(
            hass, bimmer.update,
            minute=range(now.minute % UPDATE_INTERVAL, 60, UPDATE_INTERVAL),
            second=now.second)

    hass.data[DOMAIN] = accounts

    for account in accounts:
        account.update()

    for component in BMW_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class BMWConnectedDriveAccount(object):
    """Representation of a BMW vehicle."""

    def __init__(self, username: str, password: str, region_str: str,
                 name: str) -> None:
        """Constructor."""
        from bimmer_connected.account import ConnectedDriveAccount
        from bimmer_connected.country_selector import get_region_from_name

        region = get_region_from_name(region_str)

        self.account = ConnectedDriveAccount(username, password, region)
        self.name = name
        self._update_listeners = []

    def update(self, *_):
        """Update the state of all vehicles.

        Notify all listeners about the update.
        """
        _LOGGER.debug('Updating vehicle state for account %s, '
                      'notifying %d listeners',
                      self.name, len(self._update_listeners))
        try:
            self.account.update_vehicle_states()
            for listener in self._update_listeners:
                listener()
        except IOError as exception:
            _LOGGER.error('Error updating the vehicle state.')
            _LOGGER.exception(exception)

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
