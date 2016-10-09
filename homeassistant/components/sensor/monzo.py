"""
Support for Monzo service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.monzo/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MONITORED_VARIABLES, CONF_ACCESS_TOKEN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['monzo==0.5.3']

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNT_ID = 'account_id'

ICONS = {
    'eur': 'mdi:currency-eur',
    'gbp': 'mdi:currency-gbp',
    'inr': 'mdi:currency-inr',
    'ngn': 'mdi:currency-ngn',
    'rub': 'mdi:currency-rub',
    'try': 'mdi:currency-try',
    'usd': 'mdi:currency-usd',
}

DEFAULT_NAME = 'Monzo'

VARIABLE_TYPES = {
    'balance': 'Balance',
    'currency': 'Currency',
    'spend_today': 'Spend today',
    'local_currency': 'Local currency',
    'local_exchange_rate': 'Local exchange rate'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['balance']):
        vol.All(cv.ensure_list, [vol.In(VARIABLE_TYPES)]),
    vol.Optional(CONF_ACCOUNT_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Monzo sensor."""
    from monzo.errors import (ForbiddenError, UnauthorizedError)
    access_token = config.get(CONF_ACCESS_TOKEN)
    account_id = config.get(CONF_ACCOUNT_ID)
    name = config.get(CONF_NAME)

    try:
        data = MonzoData(access_token, account_id)
    except (ForbiddenError, UnauthorizedError):
        _LOGGER.error('Monzo failed to initialise', exec=True)
        return False

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(MonzoSensor(data, variable, name))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class MonzoSensor(Entity):
    """Representation of a Monzo sensor."""

    def __init__(self, data, variable, name):
        """Initialize the sensor."""
        self.client_name = name
        self.data = data
        self.type = variable
        self._name = VARIABLE_TYPES[variable]
        self._unit_of_measurement = None
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        unit = self._unit_of_measurement

        if not unit:
            return ICONS['usd']

        icon = ([k for k, v in ICONS.items() if unit.lower() in v][0])

        if icon:
            return icon
        else:
            return ICONS['usd']

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        balance = self.data.balance

        if self.type == 'balance':
            self._state = balance['balance']
            self._unit_of_measurement = balance['currency']
        elif self.type == 'currency':
            self._state = balance['currency']
        elif self.type == 'spend_today':
            self._state = balance['spend_today']
            self._unit_of_measurement = balance['currency']
        elif self.type == 'local_currency':
            self._state = balance['local_currency']
        elif self.type == 'local_exchange_rate':
            self._state = balance['local_exchange_rate']
            self._unit_of_measurement = balance['currency']


class MonzoData(object):
    """Get the latest data and update the states."""

    def __init__(self, access_token, account_id):
        """Initialize the data object."""
        from monzo.monzo import Monzo

        self._monzo = Monzo(access_token)
        if account_id:
            self._account_id = account_id
        else:
            self._account_id = self._monzo.get_first_account()['id']
        self.balance = None
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Monzo."""
        self.balance = self._monzo.get_balance(self._account_id)
