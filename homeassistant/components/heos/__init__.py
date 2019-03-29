"""Denon HEOS Media Player."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import format_title
from .const import DATA_CONTROLLER, DOMAIN

REQUIREMENTS = ['pyheos==0.2.0']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the HEOS component."""
    host = config[DOMAIN][CONF_HOST]
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        # Create new entry based on config
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={'source': 'import'},
                data={CONF_HOST: host}))
    else:
        # Check if host needs to be updated
        entry = entries[0]
        if entry.data[CONF_HOST] != host:
            entry.data[CONF_HOST] = host
            entry.title = format_title(host)
            hass.config_entries.async_update_entry(entry)

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Initialize config entry which represents the HEOS controller."""
    from pyheos import Heos
    host = entry.data[CONF_HOST]
    # Setting all_progress_events=False ensures that we only receive a
    # media position update upon start of playback or when media changes
    controller = Heos(host, all_progress_events=False)
    try:
        await controller.connect(auto_reconnect=True)
    # Auto reconnect only operates if initial connection was successful.
    except (asyncio.TimeoutError, ConnectionError) as error:
        await controller.disconnect()
        _LOGGER.exception("Unable to connect to controller %s: %s",
                          host, type(error).__name__)
        return False

    async def disconnect_controller(event):
        await controller.disconnect()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_controller)

    try:
        players = await controller.get_players()
    except (asyncio.TimeoutError, ConnectionError) as error:
        await controller.disconnect()
        _LOGGER.exception("Unable to retrieve players: %s",
                          type(error).__name__)
        return False

    hass.data[DOMAIN] = {
        DATA_CONTROLLER: controller,
        MEDIA_PLAYER_DOMAIN: players
    }
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, MEDIA_PLAYER_DOMAIN))
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER]
    await controller.disconnect()
    hass.data.pop(DOMAIN)
    return await hass.config_entries.async_forward_entry_unload(
        entry, MEDIA_PLAYER_DOMAIN)
