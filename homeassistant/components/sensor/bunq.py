"""
Support for balance data via the Bunq Bank API.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.bunq/
"""
import asyncio
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_PREFIX
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['bunq-sdk==1.1.0']

_LOGGER = logging.getLogger(__name__)

# minutes between refreshes
INTERVAL_TO_NEXT_REFRESH = 120

CONF_ACCOUNTS = 'accounts'
CONF_SANDBOX = 'sandbox'

DEFAULT_SANDBOX = False
DEFAULT_PREFIX = 'Bunq'

ICON = 'mdi:currency-eur'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
    vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Bunq Bank sensor platform."""
    from bunq.sdk.context import (
        ApiContext, ApiEnvironmentType, BunqContext)
    from bunq.sdk.model.generated import endpoint
    from bunq.sdk.json import converter

    api_environment = ApiEnvironmentType.SANDBOX \
        if config.get(CONF_SANDBOX) else ApiEnvironmentType.PRODUCTION

    accs = []
    try:
        bunq_context = ApiContext(
            api_environment,
            config.get(CONF_API_KEY),
            'Home Assistant'
        )
        bunq_context.ensure_session_active()
        BunqContext.load_api_context(bunq_context)
        accounts = converter.serialize(
            endpoint.MonetaryAccount.list().value)
        accs = [BunqAccountSensor(
            (config.get(CONF_PREFIX) + ' ' if config.get(CONF_PREFIX) else '')
            + a['MonetaryAccountBank']['description'],
            a['MonetaryAccountBank']['id'],
            a['MonetaryAccountBank']['currency']
            ) for a in accounts]
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(
            "Unable to set up Bunq account: %s", error)
    async_add_entities(accs)

    data = BunqData(hass, bunq_context, accs)
    # schedule the first update in 1 minute from now:
    await data.schedule_update(1)


class BunqAccountSensor(Entity):
    """Representation of a Bunq balance sensor."""

    def __init__(self, account_name, account_id, currency):
        """Initialize the sensor."""
        self._account_name = account_name
        self._account_id = account_id
        self._currency = currency
        self._state = None

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
            self._state = data.get(self._account_id, None)
            return True
        except KeyError:
            self._state = None
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
        if self._bunq_accounts:
            tasks = []
            # Update all devices
            for acc in self._bunq_accounts:
                if acc.load_data(self.data):
                    tasks.append(acc.async_update_ha_state())
            if tasks:
                await asyncio.wait(tasks, loop=self.hass.loop)

    async def schedule_update(self, minute=1):
        """Schedule an update after minute minutes."""
        _LOGGER.debug("Scheduling next update in %s minutes.", minute)
        nxt = dt_util.utcnow() + timedelta(minutes=minute)
        async_track_point_in_utc_time(self.hass, self.async_update,
                                      nxt)

    async def async_update(self, *_):
        """Update the data from bunq."""
        from bunq.sdk.context import BunqContext, BunqException
        from bunq.sdk.model.generated import endpoint
        from bunq.sdk.json import converter
        BunqContext.load_api_context(self._bunq_context)
        try:
            accounts = converter.serialize(
                endpoint.MonetaryAccount.list().value)
            self.data = {
                a['MonetaryAccountBank']['id']:
                float(a['MonetaryAccountBank']['balance']['value'])
                for a in accounts}
            await self.update_devices()
        except KeyError:
            _LOGGER.warning('Count not find key in API result.')
        except BunqException as err:
            _LOGGER.error(
                'Bunq returned an exception during the call. %s', err)
        finally:
            await self.schedule_update(INTERVAL_TO_NEXT_REFRESH)
