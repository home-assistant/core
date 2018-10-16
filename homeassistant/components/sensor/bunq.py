"""
Support for balance data via the Bunq Bank API.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.bunq/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['bunq-sdk==1.1.0']

_LOGGER = logging.getLogger(__name__)

# minutes between refreshes
INTERVAL_TO_NEXT_REFRESH = 120

CONF_SANDBOX = 'sandbox'
DEFAULT_SANDBOX = False

ICON = 'mdi:currency-eur'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Bunq Bank sensor platform."""
    from bunq.sdk.context import (
        ApiContext, ApiEnvironmentType,
        BunqContext)
    from bunq.sdk.exception import BunqException, ApiException
    from bunq.sdk.model.generated import endpoint
    from bunq.sdk.json import converter

    # set environment type
    api_environment = ApiEnvironmentType.SANDBOX \
        if config.get(CONF_SANDBOX) else ApiEnvironmentType.PRODUCTION

    accs = []
    try:
        # create the api context variable
        bunq_context = ApiContext(
            api_environment,
            config.get(CONF_API_KEY),
            'Home Assistant'
        )
        # ensure the key is active, or activate
        bunq_context.ensure_session_active()
        # load user context from api context (not IO)
        # checks if the user has active accounts
        # raises BunqException otherwise

        BunqContext.load_api_context(bunq_context)
        # call the account list endpoint
        accounts = converter.serialize(
            endpoint.MonetaryAccount.list().value)
        # create and add the devices to the list
        for acc in accounts:
            accs.append(BunqAccountSensor(
                acc['MonetaryAccountBank']['description'],
                acc['MonetaryAccountBank']['id'],
                acc['MonetaryAccountBank']['currency'],
                float(acc['MonetaryAccountBank']['balance']['value'])
                ))
        async_add_entities(accs)
        # create the refresh object
        data = BunqData(hass, bunq_context, accs)
        # schedule the first update
        await data.schedule_update(INTERVAL_TO_NEXT_REFRESH)
    except ApiException as err:
        # if there is something wrong with the user setup
        # such as a incorrect key or invalid IP address
        # log the error and raise HA error
        # nothing to setup further until the key is changed
        _LOGGER.error(err)
    except BunqException as err:
        # if the Bunq sdk errors out there is
        # such as API rate limit throtteling
        # log the error and raise PlatformNotReady to retry
        _LOGGER.error(err)
        raise PlatformNotReady


class BunqAccountSensor(Entity):
    """Representation of a Bunq balance sensor."""

    def __init__(self, account_name, account_id, currency, balance):
        """Initialize the sensor."""
        self._account_name = account_name
        self._account_id = account_id
        self._currency = currency
        # since the call in setup to get accounts
        # includes balances, we can initizalize with the state
        self._state = balance

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._account_id

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

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def load_data(self, data):
        """Load the sensor with relevant data."""
        try:
            # store the current balance
            old_balance = self._state
            # write the new balance to state
            self._state = data.get(self._account_id, None)
            # return False if nothing has changed, true otherwise
            return False if self._state == old_balance else True
        except KeyError:
            self._state = None
            _LOGGER.warning('Count not find key in API results.')
            return False


class BunqData:
    """Get the latest data and updates the states."""

    def __init__(self, hass, bunq_context, bunq_accounts):
        """Initialize the data object."""
        self._bunq_context = bunq_context
        self._bunq_accounts = bunq_accounts
        self.data = {}
        self.hass = hass

    async def update_devices(self):
        """Update all devices/sensors."""
        if not self._bunq_accounts:
            return
        tasks = []
        # Update all devices
        for acc in self._bunq_accounts:
            # if the old and new balances where the same
            # there is no need to call the state update method
            if acc.load_data(self.data):
                tasks.append(acc.async_update_ha_state())
        if tasks:
            await asyncio.wait(tasks, loop=self.hass.loop)

    async def schedule_update(self, minute=1):
        """Schedule an update after minute minutes."""
        _LOGGER.debug("Scheduling next update in {} minutes.".format(minute))
        async_track_time_interval(
            self.hass, self.async_update, timedelta(minutes=minute))

    async def async_update(self, *_):
        """Update the data from bunq."""
        from bunq.sdk.exception import BunqException, ApiException
        from bunq.sdk.model.generated import endpoint
        from bunq.sdk.json import converter

        try:
            # get the account list which includes the balance
            accounts = await self.hass.async_add_executor_job(
                converter.serialize, endpoint.MonetaryAccount.list().value)
            # create a dict with the id and the balance value
            self.data = {
                a['MonetaryAccountBank']['id']:
                float(a['MonetaryAccountBank']['balance']['value'])
                for a in accounts}
            # update the individual sensors
            await self.update_devices()
        except KeyError:
            # if the key (the account id) is not found warn
            # can happen when a account is deleted in Bunq
            # but still present in HA
            _LOGGER.warning('Count not find account in API results.')
        except (BunqException, ApiException) as err:
            # if the Bunq sdk errors out there is
            # something wrong with the user setup
            # or the api call
            # log the error and raise HA error
            _LOGGER.error(err)
        finally:
            # schedule the next refresh (default 2 hours)
            await self.schedule_update(INTERVAL_TO_NEXT_REFRESH)
