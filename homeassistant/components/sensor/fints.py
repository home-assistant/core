"""
Read the balance of your bank accounts via FinTS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fints/
"""

from collections import namedtuple
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PIN, CONF_URL, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['fints==0.2.1']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)
ICON = 'mdi:currency-eur'

BankCredentials = namedtuple('BankCredentials', 'blz login pin url')

CONF_BIN = 'bank_identification_number'
CONF_ACCOUNTS = 'accounts'
CONF_IBAN = 'iban'

SCHEMA_ACCOUNTS = vol.Schema({
    vol.Required(CONF_IBAN): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BIN): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PIN): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ACCOUNTS, default=[]): cv.ensure_list(SCHEMA_ACCOUNTS),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensors.

    Login to the bank and get a list of existing accounts. Create a
    sensor for each account.
    """
    credentials = BankCredentials(config[CONF_BIN], config[CONF_USERNAME],
                                  config[CONF_PIN], config[CONF_URL])
    fints_name = config[CONF_NAME]

    account_config = dict()
    for acc in config[CONF_ACCOUNTS]:
        account_config[acc[CONF_IBAN]] = acc[CONF_NAME]

    bank = _connect(credentials)
    accounts = []
    # filter out accounts without IBAN
    for account in [a for a in bank.get_sepa_accounts() if a.iban]:
        if not config[CONF_ACCOUNTS] or account.iban in account_config:
            account_name = account_config.get(account.iban)
            if not account_name:
                account_name = '{} - {}'.format(fints_name, account.iban)
            accounts += [FinTsAccount(credentials, account.iban, account_name)]
            _LOGGER.debug('Creating account %s for bank %s',
                          account.iban, fints_name)

    add_devices(accounts, True)


def _connect(credentials: BankCredentials):
    """Connect to the bank."""
    from fints.client import FinTS3PinTanClient
    _LOGGER.debug('Connecting to account %s', credentials.login)
    bank = FinTS3PinTanClient(credentials.blz, credentials.login,
                              credentials.pin, credentials.url)
    return bank


class FinTsAccount(Entity):
    """Sensor for a FinTS Account."""

    def __init__(self, credentials: BankCredentials, iban: str, name: str):
        self._credentials = credentials  # type: BankCredentials
        self._iban = iban  # type: str
        self._name = name  # type: str
        self._balance = None   # type: float
        self._currency = None  # type: str

    @property
    def should_poll(self):
        """Data needs to be polled from the bank servers."""
        return True

    def update(self):
        """Get the current balance any currency for the account."""
        bank = _connect(self._credentials)
        for account in bank.get_sepa_accounts():
            if self._iban == account.iban or \
                    self._iban == account.accountnumber:
                balance = bank.get_balance(account)
                self._balance = balance.amount.amount
                self._currency = balance.amount.currency
                _LOGGER.debug('updated balance of account %s', self.name)
                return
        _LOGGER.warning('Could not find new balance for account %s', self.name)
        self._balance = None
        self._currency = None

    @property
    def name(self):
        """Friendly name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the balance of the account as state."""
        return self._balance

    @property
    def unit_of_measurement(self):
        """Use the currency as unit of measurement."""
        return self._currency

    @property
    def device_state_attributes(self):
        """Additional attributes of the sensor."""
        return {
            'IBAN': self._iban
        }

    @property
    def icon(self):
        """Set the icon for the sensor."""
        return ICON
