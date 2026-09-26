"""Support for monitoring OctoPrint 3D printers."""

import logging

import aiohttp
import probatio
from pyoctoprintapi import OctoprintClient

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify as util_slugify
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import DOMAIN
from .coordinator import OctoprintConfigEntry, OctoprintDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer["name"]) for printer in value]
    probatio.Schema(probatio.Unique())(names)
    return value


def ensure_valid_path(value):
    """Validate the path, ensuring it starts and ends with a /."""
    probatio.Schema(cv.string)(value)
    if value[0] != "/":
        value = f"/{value}"
    if value[-1] != "/":
        value += "/"
    return value


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.SENSOR,
]
DEFAULT_NAME = "OctoPrint"
CONF_NUMBER_OF_TOOLS = "number_of_tools"
CONF_BED = "bed"

BINARY_SENSOR_TYPES = [
    "Printing",
    "Printing Error",
]

BINARY_SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): probatio.All(cv.ensure_list, [probatio.In(BINARY_SENSOR_TYPES)]),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSOR_TYPES = [
    "Temperatures",
    "Current State",
    "Job Percentage",
    "Time Remaining",
    "Time Elapsed",
]

SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)
        ): probatio.All(cv.ensure_list, [probatio.In(SENSOR_TYPES)]),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    probatio.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: probatio.All(
                cv.ensure_list,
                [
                    probatio.Schema(
                        {
                            probatio.Required(CONF_API_KEY): cv.string,
                            probatio.Required(CONF_HOST): cv.string,
                            probatio.Optional(CONF_SSL, default=False): cv.boolean,
                            probatio.Optional(CONF_PORT, default=80): cv.port,
                            probatio.Optional(
                                CONF_PATH, default="/"
                            ): ensure_valid_path,
                            # Following values are not longer used in the configuration
                            # of the integration and are here for historical purposes
                            probatio.Optional(
                                CONF_NAME, default=DEFAULT_NAME
                            ): cv.string,
                            probatio.Optional(
                                CONF_NUMBER_OF_TOOLS, default=0
                            ): cv.positive_int,
                            probatio.Optional(CONF_BED, default=False): cv.boolean,
                            probatio.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                            probatio.Optional(
                                CONF_BINARY_SENSORS, default={}
                            ): BINARY_SENSOR_SCHEMA,
                        }
                    )
                ],
                has_all_unique_names,
            )
        },
    ),
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OctoPrint component."""
    async_setup_services(hass)
    if DOMAIN not in config:
        return True

    domain_config = config[DOMAIN]

    for conf in domain_config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_API_KEY: conf[CONF_API_KEY],
                    CONF_HOST: conf[CONF_HOST],
                    CONF_PATH: conf[CONF_PATH],
                    CONF_PORT: conf[CONF_PORT],
                    CONF_SSL: conf[CONF_SSL],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OctoprintConfigEntry) -> bool:
    """Set up OctoPrint from a config entry."""
    if CONF_VERIFY_SSL not in entry.data:
        data = {**entry.data, CONF_VERIFY_SSL: True}
        hass.config_entries.async_update_entry(entry, data=data)

    connector = aiohttp.TCPConnector(
        force_close=True,
        ssl=get_default_no_verify_context()
        if not entry.data[CONF_VERIFY_SSL]
        else get_default_context(),
    )
    session = aiohttp.ClientSession(connector=connector)

    @callback
    def _async_close_websession(event: Event | None = None) -> None:
        """Close websession."""
        session.detach()

    entry.async_on_unload(_async_close_websession)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_close_websession)
    )

    client = OctoprintClient(
        host=entry.data[CONF_HOST],
        session=session,
        port=entry.data[CONF_PORT],
        ssl=entry.data[CONF_SSL],
        path=entry.data[CONF_PATH],
    )

    client.set_api_key(entry.data[CONF_API_KEY])

    coordinator = OctoprintDataUpdateCoordinator(hass, client, entry, 30)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OctoprintConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
