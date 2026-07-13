"""Support for a Genius Hub system."""

from datetime import timedelta
import logging

import aiohttp
from geniushubclient import GeniusHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import setup_service_functions

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)

MAC_ADDRESS_REGEXP = r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


type GeniusHubConfigEntry = ConfigEntry[GeniusBroker]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Genius Hub services."""
    setup_service_functions(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GeniusHubConfigEntry) -> bool:
    """Create a Genius Hub system."""
    if CONF_TOKEN in entry.data and CONF_MAC in entry.data:
        entity_registry = er.async_get(hass)
        registry_entries = er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        for reg_entry in registry_entries:
            if reg_entry.unique_id.startswith(entry.data[CONF_MAC]):
                entity_registry.async_update_entity(
                    reg_entry.entity_id,
                    new_unique_id=reg_entry.unique_id.replace(
                        entry.data[CONF_MAC], entry.entry_id
                    ),
                )

    session = async_get_clientsession(hass)
    if CONF_HOST in entry.data:
        client = GeniusHub(
            entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
    else:
        client = GeniusHub(entry.data[CONF_TOKEN], session=session)

    unique_id = entry.unique_id or entry.entry_id

    broker = entry.runtime_data = GeniusBroker(hass, client, unique_id)

    try:
        await client.update()
    except aiohttp.ClientResponseError as err:
        _LOGGER.error("Setup failed, check your configuration, %s", err)
        return False
    broker.make_debug_log_entries()

    async_track_time_interval(hass, broker.async_update, SCAN_INTERVAL)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class GeniusBroker:
    """Container for geniushub client and data."""

    def __init__(self, hass: HomeAssistant, client: GeniusHub, hub_uid: str) -> None:
        """Initialize the geniushub client."""
        self.hass = hass
        self.client = client
        self.hub_uid = hub_uid
        self._connect_error = False

    async def async_update(self, now, **kwargs) -> None:
        """Update the geniushub client's data."""
        try:
            await self.client.update()
            if self._connect_error:
                self._connect_error = False
                _LOGGER.warning("Connection to geniushub re-established")
        except (
            aiohttp.ClientResponseError,
            aiohttp.client_exceptions.ClientConnectorError,
        ) as err:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Connection to geniushub failed (unable to update), message is: %s",
                    err,
                )
            return
        self.make_debug_log_entries()

        async_dispatcher_send(self.hass, DOMAIN)

    def make_debug_log_entries(self) -> None:
        """Make any useful debug log entries."""
        _LOGGER.debug(
            "Raw JSON: \n\nclient._zones = %s \n\nclient._devices = %s",
            self.client._zones,  # noqa: SLF001
            self.client._devices,  # noqa: SLF001
        )
