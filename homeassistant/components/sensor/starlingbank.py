"""
Support for balance data via the Starling Bank API.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.starlingbank/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['starlingbank==3.1']

_LOGGER = logging.getLogger(__name__)

BALANCE_TYPES = ['cleared_balance', 'effective_balance']

CONF_ACCOUNTS = 'accounts'
CONF_BALANCE_TYPES = 'balance_types'
CONF_SANDBOX = 'sandbox'

DEFAULT_SANDBOX = False
DEFAULT_ACCOUNT_NAME = 'Starling'

ICON = 'mdi:currency-gbp'

ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_BALANCE_TYPES, default=BALANCE_TYPES):
        vol.All(cv.ensure_list, [vol.In(BALANCE_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_ACCOUNT_NAME): cv.string,
    vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCOUNTS): vol.Schema([ACCOUNT_SCHEMA]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sterling Bank sensor platform."""
    from starlingbank import StarlingAccount

    sensors = []
    for account in config[CONF_ACCOUNTS]:
        try:
            starling_account = StarlingAccount(
                account[CONF_ACCESS_TOKEN], sandbox=account[CONF_SANDBOX])
            for balance_type in account[CONF_BALANCE_TYPES]:
                sensors.append(StarlingBalanceSensor(
                    starling_account, account[CONF_NAME], balance_type))
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(
                "Unable to set up Starling account '%s': %s",
                account[CONF_NAME], error)

    add_devices(sensors, True)


class StarlingBalanceSensor(Entity):
    """Representation of a Starling balance sensor."""

    def __init__(self, starling_account, account_name, balance_data_type):
        """Initialize the sensor."""
        self._starling_account = starling_account
        self._balance_data_type = balance_data_type
        self._state = None
        self._account_name = account_name

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{0} {1}".format(
            self._account_name,
            self._balance_data_type.replace('_', ' ').capitalize())

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._starling_account.currency

    @property
    def icon(self):
        """Return the entity icon."""
        return ICON

    def update(self):
        """Fetch new state data for the sensor."""
        self._starling_account.update_balance_data()
        if self._balance_data_type == 'cleared_balance':
            self._state = self._starling_account.cleared_balance / 100
        elif self._balance_data_type == 'effective_balance':
            self._state = self._starling_account.effective_balance / 100
