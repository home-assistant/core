"""The flunearyou component."""
import asyncio
from datetime import timedelta

from pyflunearyou import Client
from pyflunearyou.errors import FluNearYouError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS
from homeassistant.exceptions import ConfigEntryNotReady
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
        DOMAIN: vol.All(
            cv.deprecated(CONF_MONITORED_CONDITIONS, invalidation_version="0.114.0"),
            vol.Schema(
                {
                    vol.Optional(CONF_LATITUDE): cv.latitude,
                    vol.Optional(CONF_LONGITUDE): cv.longitude,
                    vol.Optional(
                        CONF_MONITORED_CONDITIONS, default=list(SENSORS)
                    ): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Flu Near You component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

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

    try:
        await fny.async_update()
    except FluNearYouError as err:
        LOGGER.error("Error while setting up integration: %s", err)
        raise ConfigEntryNotReady

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
        self._client = client
        self._hass = hass
        self.data = {}
        self.latitude = latitude
        self.longitude = longitude

    async def async_update(self):
        """Update Flu Near You data."""
        tasks = {
            CATEGORY_CDC_REPORT: self._client.cdc_reports.status_by_coordinates(
                self.latitude, self.longitude
            ),
            CATEGORY_USER_REPORT: self._client.user_reports.status_by_coordinates(
                self.latitude, self.longitude
            ),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for category, result in zip(tasks, results):
            if isinstance(result, FluNearYouError):
                LOGGER.error("Error while retrieving %s data: %s", category, result)
                continue
            self.data[category] = result

        LOGGER.debug("Received new data")
        async_dispatcher_send(self._hass, TOPIC_UPDATE)
