"""The bluesound component."""

from dataclasses import dataclass

from pyblu import Player, SyncStatus
from pyblu.errors import PlayerUnreachableError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.MEDIA_PLAYER]


@dataclass
class BluesoundRuntimeData:
    """Bluesound data class."""

    player: Player
    sync_status: SyncStatus


type BluesoundConfigEntry = ConfigEntry[BluesoundRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = []
    setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: BluesoundConfigEntry
) -> bool:
    """Set up the Bluesound entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    session = async_get_clientsession(hass)
    async with Player(host, port, session=session, default_timeout=10) as player:
        try:
            sync_status = await player.sync_status(timeout=1)
        except PlayerUnreachableError as ex:
            raise ConfigEntryNotReady(f"Error connecting to {host}:{port}") from ex

    config_entry.runtime_data = BluesoundRuntimeData(player, sync_status)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
