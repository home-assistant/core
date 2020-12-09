"""Support for balance data via the Investec Bank API."""
from datetime import timedelta
import logging

from investec import InvestecClient
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

CONF_ACCOUNTS = "accounts"
CONF_DATA = "data"
CONF_ACCOUNT_NAME = "accountName"
CONF_ACCOUNT_BALANCE = "account_balance"
CONF_ACCOUNT_ID = "accountId"
CONF_CURRENCY = "currency"
CONF_CURRENT_BALANCE = "currentBalance"
CONF_ACCOUNT_NUMBER = "accountNumber"

ICON = "mdi:cash-multiple"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Investec sensor platform."""
    sensors = []

    investec_client = InvestecClient(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET])

    sub_accounts = investec_client.access_bank(CONF_ACCOUNTS)[CONF_DATA][CONF_ACCOUNTS]

    for sub_account in sub_accounts:
        sensors.append(InvestecBalanceSensor(investec_client, sub_account))

    add_entities(sensors, True)


class InvestecBalanceSensor(Entity):
    """Representation of a Investec balance sensor."""

    def __init__(self, investec_client, sub_account):
        """Initialize the sensor."""
        self._investec_client = investec_client
        self._account = sub_account
        self._account_id = self._account[CONF_ACCOUNT_ID]
        self._account_name = "{}-{}".format(
            self._account[CONF_ACCOUNT_NAME], self._account[CONF_ACCOUNT_NUMBER]
        )
        self._currency = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._account_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._currency

    @property
    def icon(self):
        """Return the entity icon."""
        return ICON

    def update(self):
        """Fetch new state data for the sensor."""
        self._state = self._investec_client.access_bank(
            CONF_ACCOUNT_BALANCE, accountId=self._account_id
        )[CONF_DATA][CONF_CURRENT_BALANCE]
        self._currency = self._investec_client.access_bank(
            CONF_ACCOUNT_BALANCE, accountId=self._account[CONF_ACCOUNT_ID]
        )[CONF_DATA][CONF_CURRENCY]
