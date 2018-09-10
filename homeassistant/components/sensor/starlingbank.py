"""
Support for balance data via the Starling Bank API.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.starlingbank/
"""
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_NAME
)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['starlingbank==1.1']

BALANCE_TYPES = ['cleared_balance', 'effective_balance']
DEFAULT_ACCOUNT_NAME = 'Starling'
ICON = 'mdi:currency-gbp'

CONF_ACCOUNTS = 'accounts'
CONF_BALANCE_TYPES = 'balance_types'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCOUNTS): vol.All([{
            vol.Optional(CONF_NAME, default=DEFAULT_ACCOUNT_NAME): cv.string,
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(
                CONF_BALANCE_TYPES, default=BALANCE_TYPES
                ): vol.All(
                    cv.ensure_list,  # Wraps value in a list if it is not one.
                    [vol.In(BALANCE_TYPES)]
                )
        }], cv.ensure_list)
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sensor platform setup."""
    from starlingbank import StarlingAccount

    sensors = []
    for account in CONF_ACCOUNTS:
        starling_account = StarlingAccount(account[CONF_ACCESS_TOKEN])
        for balance_type in account[CONF_BALANCE_TYPES]:
            sensors.append(StarlingBalanceSensor(
                starling_account,
                account[CONF_NAME],
                balance_type
            ))
    add_devices(sensors, True)  # True forces an update upon platform setup.


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
        if self._balance_data_type == 'effective_balance':
            name = "Effective Balance"
        else:
            name = "Cleared Balance"
        return "{0} {1}".format(self._account_name, name)

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
        self._starling_account.balance.update()
        if self._balance_data_type == 'cleared_balance':
            self._state = self._starling_account.balance.cleared_balance
        elif self._balance_data_type == 'effective_balance':
            self._state = self._starling_account.balance.effective_balance
