"""Support for bunq account balance."""
import asyncio
from datetime import timedelta
import logging

from bunq.sdk.context import ApiContext, ApiEnvironmentType, BunqContext
from bunq.sdk.exception import ApiException, BunqException
from bunq.sdk.model.generated import endpoint
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

ICON = "mdi:cash-multiple"
UPDATE_INTERVAL = 60

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up bunq sensors."""
    sensors = []

    # setup api
    api_context = ApiContext(
        ApiEnvironmentType.PRODUCTION, config.get(CONF_API_KEY), "Home Assistant",
    )
    api_context.ensure_session_active()
    BunqContext.load_api_context(api_context)

    # create sensors
    try:
        for account in get_account_data():
            sensors.append(BunqBalanceSensor(account))
    except (ApiException, BunqException) as err:
        _LOGGER.error(err)

    async_add_entities(sensors, True)

    # schedule updates for sensors
    data = BunqData(hass, api_context, sensors)
    await data.schedule_update(UPDATE_INTERVAL)


def get_account_data():
    """Get active bunq accounts."""
    active_accounts = []

    accounts = endpoint.MonetaryAccountBank.list().value
    for account in accounts:
        if account.status == "ACTIVE":
            active_accounts.append(account)

    return active_accounts


class BunqBalanceSensor(Entity):
    """Setup bunq balance sensor."""

    def __init__(self, account):
        """Initialize the sensor."""
        self.id = account.id_
        self._name = account.description
        self._state = float(account.balance.value)
        self._unit_of_measurement = account.currency

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the entity icon."""
        return ICON

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def load_data(self, data):
        """Update sensor data."""
        try:
            old_balance = self._state
            self._state = data.get(self.id)
            return False if self._state == old_balance else True
        except KeyError:
            self._state = None
            _LOGGER.warning("Count not find key in API results.")
            return False


class BunqData:
    """Get the latest data and updates the sensors."""

    def __init__(self, hass, api_context, sensors):
        """Initialize the data object."""
        self._api_context = api_context
        self._sensors = sensors
        self.data = {}
        self.hass = hass

    async def update_devices(self):
        """Update all sensors."""
        tasks = []

        for sensor in self._sensors:
            if sensor.load_data(self.data):
                tasks.append(sensor.async_update_ha_state())
        if tasks:
            await asyncio.wait(tasks)

    async def schedule_update(self, seconds):
        """Schedule an update."""
        async_track_time_interval(
            self.hass, self.async_update, timedelta(seconds=seconds)
        )

    async def async_update(self, *_):
        """Update data."""
        try:
            # get new data from api
            accounts = get_account_data()

            # create a dict with account id as key and account data as value
            self.data = {
                account.id_: float(account.balance.value) for account in accounts
            }

            # update the sensors
            await self.update_devices()
        except KeyError:
            _LOGGER.warning("Bunq account not found.")
        except (ApiException, BunqException) as err:
            _LOGGER.error(err)
