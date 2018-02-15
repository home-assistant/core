"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/bmw_connected_drive/
"""
import logging
import asyncio
from random import randint

import voluptuous as vol
from homeassistant.helpers import discovery
from homeassistant.helpers.event import async_track_utc_time_change

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD
)

REQUIREMENTS = ['bimmer_connected==0.2.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'bmw_connected_drive'
CONF_VALUES = 'values'
CONF_COUNTRY = 'country'

LENGTH_ATTRIBUTES = [
    'remaining_range_fuel',
    'mileage',
    ]

VAILD_ATTRIBUTES = LENGTH_ATTRIBUTES + [
    'timestamp',
    'remaining_fuel',
]

ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_COUNTRY): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: ACCOUNT_SCHEMA
    },
}, extra=vol.ALLOW_EXTRA)


BMW_COMPONENTS = ['device_tracker', 'sensor']


def setup(hass, config):
    """Set up the BMW connected drive components."""
    accounts = []
    for name, account_config in config[DOMAIN].items():
        username = account_config[CONF_USERNAME]
        password = account_config[CONF_PASSWORD]
        country = account_config[CONF_COUNTRY]
        _LOGGER.debug('Adding new account %s', name)
        bimmer = BMWConnectedDriveEntity(hass, username, password, country, name)
        accounts.append(bimmer)

        # update every 5 minutes, select second randomly to reduce server
        # load
        async_track_utc_time_change(
            hass, bimmer.async_update, minute=range(0, 60, 5),
            second=randint(0, 59))

    hass.data[DOMAIN] = accounts

    for account in accounts:
        account.async_update()

    for component in BMW_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class BMWConnectedDriveEntity(object):
    """Representation of a BMW vehicle."""

    def __init__(self, hass, username: str, password: str, country: str,
                 name: str) -> None:
        """Constructor."""
        from bimmer_connected import ConnectedDriveAccount

        self._hass = hass
        self.account = ConnectedDriveAccount(username, password, country)
        self.name = name
        self._update_listeners = []

    @asyncio.coroutine
    def async_update(self, *_):
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
