"""The flunearyou component."""
import asyncio
from datetime import timedelta

from pyflunearyou import Client
from pyflunearyou.errors import FluNearYouError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CATEGORY_CDC_REPORT,
    CATEGORY_USER_REPORT,
    DATA_CLIENT,
    DOMAIN,
    LOGGER,
    SENSORS,
    TOPIC_UPDATE,
)

DATA_LISTENER = "listener"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_LATITUDE): cv.latitude,
                vol.Optional(CONF_LONGITUDE): cv.longitude,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def async_get_api_category(sensor_type):
    """Get the category that a particular sensor type belongs to."""
    try:
        return next(
            (
                category
                for category, sensors in SENSORS.items()
                for sensor in sensors
                if sensor[0] == sensor_type
            )
        )
    except StopIteration:
        raise ValueError(f"Can't find category sensor type: {sensor_type}")


async def async_setup(hass, config):
    """Set up the Flu Near You component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}, DATA_LISTENER: {}}

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: config[DOMAIN].get(CONF_LATITUDE, hass.config.latitude),
                CONF_LONGITUDE: config[DOMAIN].get(
                    CONF_LATITUDE, hass.config.longitude
                ),
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Flu Near You as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    fny = FluNearYouData(
        hass,
        Client(websession),
        config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
        config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
    )
    await fny.async_update()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = fny

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    async def refresh(event_time):
        """Refresh data from Flu Near You."""
        await fny.async_update()

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an Flu Near You config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    remove_listener()

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    return True


class FluNearYouData:
    """Define a data object to retrieve info from Flu Near You."""

    def __init__(self, hass, client, latitude, longitude):
        """Initialize."""
        self._async_cancel_time_interval_listener = None
        self._client = client
        self._hass = hass
        self.data = {}
        self.latitude = latitude
        self.longitude = longitude

        self._api_category_count = {
            CATEGORY_CDC_REPORT: 0,
            CATEGORY_USER_REPORT: 0,
        }

        self._api_category_locks = {
            CATEGORY_CDC_REPORT: asyncio.Lock(),
            CATEGORY_USER_REPORT: asyncio.Lock(),
        }

    async def _async_get_data_from_api(self, api_category):
        """Update and save data for a particular API category."""
        if self._api_category_count[api_category] == 0:
            return

        if api_category == CATEGORY_CDC_REPORT:
            api_coro = self._client.cdc_reports.status_by_coordinates(
                self.latitude, self.longitude
            )
        else:
            api_coro = self._client.user_reports.status_by_coordinates(
                self.latitude, self.longitude
            )

        try:
            self.data[api_category] = await api_coro
        except FluNearYouError as err:
            LOGGER.error("Unable to get %s data: %s", api_category, err)
            self.data[api_category] = None

    async def _async_update_listener_action(self, now):
        """Define an async_track_time_interval action to update data."""
        await self.async_update()

    @callback
    def async_deregister_api_interest(self, sensor_type):
        """Decrement the number of entities with data needs from an API category."""
        # If this deregistration should leave us with no registration at all, remove the
        # time interval:
        if sum(self._api_category_count.values()) == 0:
            if self._async_cancel_time_interval_listener:
                self._async_cancel_time_interval_listener()
                self._async_cancel_time_interval_listener = None
            return

        api_category = async_get_api_category(sensor_type)
        self._api_category_count[api_category] -= 1

    async def async_register_api_interest(self, sensor_type):
        """Increment the number of entities with data needs from an API category."""
        # If this is the first registration we have, start a time interval:
        if not self._async_cancel_time_interval_listener:
            self._async_cancel_time_interval_listener = async_track_time_interval(
                self._hass,
                self._async_update_listener_action,
                DEFAULT_SCAN_INTERVAL,
            )

        api_category = async_get_api_category(sensor_type)
        self._api_category_count[api_category] += 1

        # If a sensor registers interest in a particular API call and the data doesn't
        # exist for it yet, make the API call and grab the data:
        async with self._api_category_locks[api_category]:
            if api_category not in self.data:
                await self._async_get_data_from_api(api_category)

    async def async_update(self):
        """Update Flu Near You data."""
        tasks = [
            self._async_get_data_from_api(api_category)
            for api_category in self._api_category_count
        ]

        await asyncio.gather(*tasks)

        LOGGER.debug("Received new data")
        async_dispatcher_send(self._hass, TOPIC_UPDATE)
