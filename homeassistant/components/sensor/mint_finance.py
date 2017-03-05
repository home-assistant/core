"""
Mint accounts sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mint/
"""
import logging
import time
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_ID, CONF_NAME, CONF_USERNAME, CONF_PASSWORD)

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['mintapi==1.23']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Intuit Mint"
CONF_ACCOUNTS = 'accounts'
CONF_THX_GUID = 'thx_guid'
CONF_SESSION = 'ius_session'
CONF_CURRENCY = "currency"

DEFAULT_NAME = 'Mint'

ICON = 'mdi:square-inc-cash'
INIT_RETRIES = 5

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_THX_GUID): cv.string,
    vol.Required(CONF_SESSION): cv.string,
    vol.Required(CONF_ACCOUNTS):
        vol.All(cv.ensure_list, [{CONF_ID: int,
                                  CONF_NAME: cv.string,
                                  CONF_CURRENCY: cv.string}]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Mint sensor."""
    from mintapi import Mint
    from mintapi.api import MintException

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    ius_session = config.get(CONF_SESSION)
    thx_guid = config.get(CONF_THX_GUID)
    accounts = config.get(CONF_ACCOUNTS)

    # Make some retries to ensure the startup
    retries = 1
    while retries <= INIT_RETRIES:
        try:
            # Init Mint client
            mint_client = Mint(username, password, ius_session, thx_guid)
            # Save new update time
            mint_client.updated = time.time()
            # Update accounts
            mint_client.initiate_account_refresh()
            break
        except MintException as exp:
            if retries > INIT_RETRIES:
                _LOGGER.error(exp)
                return
            # retrying
            retries += 1
            _LOGGER.info("Mint init failed. "
                         "Retrying (Try %d/%d)", retries, INIT_RETRIES)

    # List accounts
    account_ids = [str(acc['accountId']) for acc in mint_client.get_accounts()
                   if acc['accountId'] is not None]
    _LOGGER.info("Mint account ids: %s", ", ".join(account_ids))

    # Prepare sensors
    dev = []
    for account in accounts:
        data = MintData(mint_client, account['id'])
        dev.append(MintSensor(data, account['name'], account['currency']))

    add_devices(dev, True)


class MintSensor(Entity):
    """Representation of a Mint sensor."""

    def __init__(self, data, account_name, currency):
        """Initialize the sensor."""
        self.data = data
        self._name = str(account_name)
        self._state = None
        self._currency = currency

    @property
    def name(self):
        """Return the name of the sensor."""
        return "mint_{}".format(self._name)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._currency

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            }

    @property
    def type(self):
        """Return the account type."""
        return self.data.type_

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._state = self.data.balance


class MintData(object):
    """Get data from Intuit Mint."""

    def __init__(self, mint_client, account_id):
        """Initialize the data object."""
        self._client = mint_client
        self._account_id = account_id
        self.balance = None
        self.name = None
        self.type_ = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and updates the states."""
        from mintapi.api import MintException
        retries = 1
        while retries <= INIT_RETRIES:
            try:
                # With store the last update time to share with
                # all sensors to avoir multiple update requests
                next_update = self._client.updated + 15 * 60
                if time.time() > next_update:
                    # Save new update time
                    self._client.updated = time.time()
                    # Update accounts
                    self._client.initiate_account_refresh()
                # Get accounts
                raw_accounts = self._client.get_accounts()
                break
            except MintException as exp:
                _LOGGER.info("Mint get account failed. Retrying "
                             "(Try %s/%s)", retries, INIT_RETRIES)
                if retries >= INIT_RETRIES:
                    _LOGGER.error(exp)
                    return
                # retrying
                retries += 1

        # Search for account
        accounts = dict([(a['accountId'], a) for a in raw_accounts])
        if self._account_id not in accounts:
            # Account not found
            account_list_msg = ", ".join([str(a) for a in accounts.keys()])
            _LOGGER.exception("Account '%s' not found. Account list: %s",
                              self._account_id, account_list_msg)
            return
        # Prepare account name
        acc_suff = accounts[self._account_id]['yodleeAccountNumberLast4'][-4:]
        self.name = "{}{}".format(self._account_id, acc_suff)
        # Get type
        self.type_ = accounts[self._account_id]['accountType']
        # Set Balance
        self.balance = accounts[self._account_id]['currentBalance']
        # Set negative balance for credit/loan accounts
        if self.type_ in ['credit', 'loan']:
            self.balance = - self.balance
