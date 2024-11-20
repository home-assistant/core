"""Support for monitoring OctoPrint 3D printers."""

from __future__ import annotations

import logging
from typing import cast

import aiohttp
from pyoctoprintapi import OctoprintClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_PROFILE_NAME,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify as util_slugify
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import CONF_BAUDRATE, DOMAIN, SERVICE_CONNECT
from .coordinator import OctoprintDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer["name"]) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


def ensure_valid_path(value):
    """Validate the path, ensuring it starts and ends with a /."""
    vol.Schema(cv.string)(value)
    if value[0] != "/":
        value = f"/{value}"
    if value[-1] != "/":
        value += "/"
    return value


PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]
DEFAULT_NAME = "OctoPrint"
CONF_NUMBER_OF_TOOLS = "number_of_tools"
CONF_BED = "bed"

BINARY_SENSOR_TYPES = [
    "Printing",
    "Printing Error",
]

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSOR_TYPES = [
    "Temperatures",
    "Current State",
    "Job Percentage",
    "Time Remaining",
    "Time Elapsed",
]

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Required(CONF_API_KEY): cv.string,
                            vol.Required(CONF_HOST): cv.string,
                            vol.Optional(CONF_SSL, default=False): cv.boolean,
                            vol.Optional(CONF_PORT, default=80): cv.port,
                            vol.Optional(CONF_PATH, default="/"): ensure_valid_path,
                            # Following values are not longer used in the configuration
                            # of the integration and are here for historical purposes
                            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                            vol.Optional(
                                CONF_NUMBER_OF_TOOLS, default=0
                            ): cv.positive_int,
                            vol.Optional(CONF_BED, default=False): cv.boolean,
                            vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                            vol.Optional(
                                CONF_BINARY_SENSORS, default={}
                            ): BINARY_SENSOR_SCHEMA,
                        }
                    )
                ],
                has_all_unique_names,
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CONNECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_PROFILE_NAME): cv.string,
        vol.Optional(CONF_PORT): cv.string,
        vol.Optional(CONF_BAUDRATE): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OctoPrint component."""
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OctoPrint from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

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
    def _async_close_websession(event: Event) -> None:
        """Close websession."""
        session.detach()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_websession)

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

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_printer_connect(call: ServiceCall) -> None:
        """Connect to a printer."""
        client = async_get_client_for_service_call(hass, call)
        await client.connect(
            printer_profile=call.data.get(CONF_PROFILE_NAME),
            port=call.data.get(CONF_PORT),
            baud_rate=call.data.get(CONF_BAUDRATE),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CONNECT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CONNECT,
            async_printer_connect,
            schema=SERVICE_CONNECT_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def async_get_client_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> OctoprintClient:
    """Get the client related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if device_entry := device_registry.async_get(device_id):
        for entry_id in device_entry.config_entries:
            if data := hass.data[DOMAIN].get(entry_id):
                return cast(OctoprintClient, data["client"])

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="missing_client",
        translation_placeholders={
            "device_id": device_id,
        },
    )
