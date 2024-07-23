"""The bluesound component."""

from pyblu import Player

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .media_player import setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound."""
    setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Bluesound entry."""
    host = config_entry.data.get(CONF_HOST)
    port = config_entry.data.get(CONF_PORT)
    try:
        async with Player(host, port) as player:
            await player.sync_status(timeout=1)
    except TimeoutError as ex:
        raise ConfigEntryNotReady(f"Timeout while connecting to {host}:{port}") from ex

    await hass.config_entries.async_forward_entry_setup(
        config_entry, Platform.MEDIA_PLAYER
    )

    return True
