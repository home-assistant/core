"""Support for balance data via the Investec Bank API."""
import logging

import requests
from investec import InvestecClient

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = "accounts"
CONF_DATA = "data"
CONF_ACCOUNT_NAME = "accountName"
CONF_ACCOUNT_BALANCE = "account_balance"
CONF_ACCOUNT_ID = "accountId"
CONF_CURRENT_BALANCE = "currentBalance"
CONF_CURRENCY = "currency"

ICON = "mdi:currency-gbp"


def setup_platform(hass, config, add_devices, discovery_info=None):
    sensors = []
    try:
        investec_client = InvestecClient(
            config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET]
        )
        sub_accounts = _GetAccounts(investec_client)

        for sub_account in sub_accounts:
            sensors.append(InvestecBalanceSensor(investec_client, sub_account))

    except requests.exceptions.HTTPError as error:
        _LOGGER.error(
            "Unable to set up Starling account '%s': %s", config[CONF_CLIENT_ID], error
        )

    add_devices(sensors, True)


def _GetAccounts(investec_client):
    return investec_client.access_bank(CONF_ACCOUNTS)[CONF_DATA][CONF_ACCOUNTS]


class InvestecBalanceSensor(Entity):
    def __init__(self, investec_client, sub_account):
        """Initialize the sensor."""
        self._investec_client = investec_client
        self._sub_account = sub_account
        self._account_id = self._sub_account[CONF_ACCOUNT_ID]
        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._sub_account[CONF_ACCOUNT_NAME]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "ZAR"
        # return self._investec_client.access_bank(
        #     CONF_ACCOUNT_BALANCE,
        #     accountId=self._sub_account[CONF_ACCOUNT_ID]
        # )[CONF_DATA][CONF_CURRENCY]

    @property
    def icon(self):
        """Return the entity icon."""
        return ICON

    @property
    def update(self):
        """Fetch new state data for the sensor."""
        self._state = self._investec_client.access_bank(
            CONF_ACCOUNT_BALANCE, accountId=self._account_id
        )[CONF_DATA][CONF_CURRENT_BALANCE]
