"""The airvisual component."""
import asyncio
import logging

from pyairvisual import Client
from pyairvisual.errors import AirVisualError, InvalidKeyError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    DATA_CLIENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

DATA_LISTENER = "listener"

DEFAULT_OPTIONS = {CONF_SHOW_ON_MAP: True}

CONF_NODE_ID = "node_id"

GEOGRAPHY_COORDINATES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
    }
)

GEOGRAPHY_PLACE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STATE): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
    }
)

CLOUD_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_GEOGRAPHIES, default=[]): vol.All(
            cv.ensure_list,
            [vol.Any(GEOGRAPHY_COORDINATES_SCHEMA, GEOGRAPHY_PLACE_SCHEMA)],
        ),
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: CLOUD_API_SCHEMA}, extra=vol.ALLOW_EXTRA)


@callback
def async_get_geography_id(geography_dict):
    """Generate a unique ID from a geography dict."""
    if CONF_CITY in geography_dict:
        return ",".join(
            (
                geography_dict[CONF_CITY],
                geography_dict[CONF_STATE],
                geography_dict[CONF_COUNTRY],
            )
        )
    return ",".join(
        (str(geography_dict[CONF_LATITUDE]), str(geography_dict[CONF_LONGITUDE]))
    )


async def async_setup(hass, config):
    """Set up the AirVisual component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up AirVisual as config entry."""
    entry_updates = {}
    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_API_KEY]
    if not config_entry.options:
        # If the config entry doesn't already have any options set, set defaults:
        entry_updates["options"] = DEFAULT_OPTIONS

    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)

    websession = aiohttp_client.async_get_clientsession(hass)

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = AirVisualData(
        hass, Client(websession, api_key=config_entry.data[CONF_API_KEY]), config_entry
    )

    try:
        await hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id].async_update()
    except InvalidKeyError:
        _LOGGER.error("Invalid API key provided")
        raise ConfigEntryNotReady

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    async def refresh(event_time):
        """Refresh data from AirVisual."""
        await hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id].async_update()

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    config_entry.add_update_listener(async_update_options)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an AirVisual config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    remove_listener()

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    return True


async def async_update_options(hass, config_entry):
    """Handle an options update."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    airvisual.async_update_options(config_entry.options)


class AirVisualData:
    """Define a class to manage data from the AirVisual cloud API."""

    def __init__(self, hass, client, config_entry):
        """Initialize."""
        self._client = client
        self._hass = hass
        self.data = {}
        self.options = config_entry.options

        self.geographies = {
            async_get_geography_id(geography): geography
            for geography in config_entry.data[CONF_GEOGRAPHIES]
        }

    async def async_update(self):
        """Get new data for all locations from the AirVisual cloud API."""
        tasks = []

        for geography in self.geographies.values():
            if CONF_CITY in geography:
                tasks.append(
                    self._client.api.city(
                        geography[CONF_CITY],
                        geography[CONF_STATE],
                        geography[CONF_COUNTRY],
                    )
                )
            else:
                tasks.append(
                    self._client.api.nearest_city(
                        geography[CONF_LATITUDE], geography[CONF_LONGITUDE],
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for geography_id, result in zip(self.geographies, results):
            if isinstance(result, AirVisualError):
                _LOGGER.error("Error while retrieving data: %s", result)
                self.data[geography_id] = {}
                continue
            self.data[geography_id] = result

        _LOGGER.debug("Received new data")
        async_dispatcher_send(self._hass, TOPIC_UPDATE)

    @callback
    def async_update_options(self, options):
        """Update the data manager's options."""
        self.options = options
        async_dispatcher_send(self._hass, TOPIC_UPDATE)
