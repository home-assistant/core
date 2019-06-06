"""Read the balance of your bank accounts via FinTS."""

from collections import namedtuple
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PIN, CONF_URL, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=4)

ICON = 'mdi:currency-eur'

BankCredentials = namedtuple('BankCredentials', 'blz login pin url')

CONF_BIN = 'bank_identification_number'
CONF_ACCOUNTS = 'accounts'
CONF_HOLDINGS = 'holdings'
CONF_ACCOUNT = 'account'

ATTR_ACCOUNT = CONF_ACCOUNT
ATTR_BANK = 'bank'
ATTR_ACCOUNT_TYPE = 'account_type'

SCHEMA_ACCOUNTS = vol.Schema({
    vol.Required(CONF_ACCOUNT): cv.string,
    vol.Optional(CONF_NAME, default=None): vol.Any(None, cv.string),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BIN): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PIN): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ACCOUNTS, default=[]): cv.ensure_list(SCHEMA_ACCOUNTS),
    vol.Optional(CONF_HOLDINGS, default=[]): cv.ensure_list(SCHEMA_ACCOUNTS),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensors.

    Login to the bank and get a list of existing accounts. Create a
    sensor for each account.
    """
    credentials = BankCredentials(config[CONF_BIN], config[CONF_USERNAME],
                                  config[CONF_PIN], config[CONF_URL])
    fints_name = config.get(CONF_NAME, config[CONF_BIN])

    account_config = {acc[CONF_ACCOUNT]: acc[CONF_NAME]
                      for acc in config[CONF_ACCOUNTS]}

    holdings_config = {acc[CONF_ACCOUNT]: acc[CONF_NAME]
                       for acc in config[CONF_HOLDINGS]}

    client = FinTsClient(credentials, fints_name)
    balance_accounts, holdings_accounts = client.detect_accounts()
    accounts = []

    for account in balance_accounts:
        if config[CONF_ACCOUNTS] and account.iban not in account_config:
            _LOGGER.info('skipping account %s for bank %s',
                         account.iban, fints_name)
            continue

        account_name = account_config.get(account.iban)
        if not account_name:
            account_name = '{} - {}'.format(fints_name, account.iban)
        accounts.append(FinTsAccount(client, account, account_name))
        _LOGGER.debug('Creating account %s for bank %s',
                      account.iban, fints_name)

    for account in holdings_accounts:
        if config[CONF_HOLDINGS] and \
                account.accountnumber not in holdings_config:
            _LOGGER.info('skipping holdings %s for bank %s',
                         account.accountnumber, fints_name)
            continue

        account_name = holdings_config.get(account.accountnumber)
        if not account_name:
            account_name = '{} - {}'.format(
                fints_name, account.accountnumber)
        accounts.append(FinTsHoldingsAccount(client, account, account_name))
        _LOGGER.debug('Creating holdings %s for bank %s',
                      account.accountnumber, fints_name)

    add_entities(accounts, True)


class FinTsClient:
    """Wrapper around the FinTS3PinTanClient.

    Use this class as Context Manager to get the FinTS3Client object.
    """

    def __init__(self, credentials: BankCredentials, name: str):
        """Initialize a FinTsClient."""
        self._credentials = credentials
        self.name = name

    @property
    def client(self):
        """Get the client object.

        As the fints library is stateless, there is not benefit in caching
        the client objects. If that ever changes, consider caching the client
        object and also think about potential concurrency problems.
        """
        from fints.client import FinTS3PinTanClient
        return FinTS3PinTanClient(
            self._credentials.blz, self._credentials.login,
            self._credentials.pin, self._credentials.url)

    def detect_accounts(self):
        """Identify the accounts of the bank."""
        from fints.dialog import FinTSDialogError
        balance_accounts = []
        holdings_accounts = []
        for account in self.client.get_sepa_accounts():
            try:
                self.client.get_balance(account)
                balance_accounts.append(account)
            except IndexError:
                # account is not a balance account.
                pass
            except FinTSDialogError:
                # account is not a balance account.
                pass
            try:
                self.client.get_holdings(account)
                holdings_accounts.append(account)
            except FinTSDialogError:
                # account is not a holdings account.
                pass

        return balance_accounts, holdings_accounts


class FinTsAccount(Entity):
    """Sensor for a FinTS balance account.

    A balance account contains an amount of money (=balance). The amount may
    also be negative.
    """

    def __init__(self, client: FinTsClient, account, name: str) -> None:
        """Initialize a FinTs balance account."""
        self._client = client  # type: FinTsClient
        self._account = account
        self._name = name  # type: str
        self._balance = None   # type: float
        self._currency = None  # type: str

    @property
    def should_poll(self) -> bool:
        """Return True.

        Data needs to be polled from the bank servers.
        """
        return True

    def update(self) -> None:
        """Get the current balance and currency for the account."""
        bank = self._client.client
        balance = bank.get_balance(self._account)
        self._balance = balance.amount.amount
        self._currency = balance.amount.currency
        _LOGGER.debug('updated balance of account %s', self.name)

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return self._name

    @property
    def state(self) -> float:
        """Return the balance of the account as state."""
        return self._balance

    @property
    def unit_of_measurement(self) -> str:
        """Use the currency as unit of measurement."""
        return self._currency

    @property
    def device_state_attributes(self) -> dict:
        """Additional attributes of the sensor."""
        attributes = {
            ATTR_ACCOUNT: self._account.iban,
            ATTR_ACCOUNT_TYPE: 'balance',
        }
        if self._client.name:
            attributes[ATTR_BANK] = self._client.name
        return attributes

    @property
    def icon(self) -> str:
        """Set the icon for the sensor."""
        return ICON


class FinTsHoldingsAccount(Entity):
    """Sensor for a FinTS holdings account.

    A holdings account does not contain money but rather some financial
    instruments, e.g. stocks.
    """

    def __init__(self, client: FinTsClient, account, name: str) -> None:
        """Initialize a FinTs holdings account."""
        self._client = client  # type: FinTsClient
        self._name = name  # type: str
        self._account = account
        self._holdings = []
        self._total = None  # type: float

    @property
    def should_poll(self) -> bool:
        """Return True.

        Data needs to be polled from the bank servers.
        """
        return True

    def update(self) -> None:
        """Get the current holdings for the account."""
        bank = self._client.client
        self._holdings = bank.get_holdings(self._account)
        self._total = sum(h.total_value for h in self._holdings)

    @property
    def state(self) -> float:
        """Return total market value as state."""
        return self._total

    @property
    def icon(self) -> str:
        """Set the icon for the sensor."""
        return ICON

    @property
    def device_state_attributes(self) -> dict:
        """Additional attributes of the sensor.

        Lists each holding of the account with the current value.
        """
        attributes = {
            ATTR_ACCOUNT: self._account.accountnumber,
            ATTR_ACCOUNT_TYPE: 'holdings',
        }
        if self._client.name:
            attributes[ATTR_BANK] = self._client.name
        for holding in self._holdings:
            total_name = '{} total'.format(holding.name)
            attributes[total_name] = holding.total_value
            pieces_name = '{} pieces'.format(holding.name)
            attributes[pieces_name] = holding.pieces
            price_name = '{} price'.format(holding.name)
            attributes[price_name] = holding.market_value

        return attributes

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement.

        Hardcoded to EUR, as the library does not provide the currency for the
        holdings. And as FinTS is only used in Germany, most accounts will be
        in EUR anyways.
        """
        return "EUR"
