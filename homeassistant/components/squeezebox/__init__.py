"""The Logitech Squeezebox integration."""

import asyncio

from pysqueezebox import async_discover

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import SOURCE_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .media_player import _LOGGER

DISCOVERY_TASK = "discovery_task"


async def start_server_discovery(hass):
    """Start a server discovery task."""

    def _discovered_server(server):
        asyncio.create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_DISCOVERY},
                data={
                    CONF_HOST: server.host,
                    CONF_PORT: int(server.port),
                    "uuid": server.uuid,
                },
            )
        )

    hass.data.setdefault(DOMAIN, {})
    if DISCOVERY_TASK not in hass.data[DOMAIN]:
        _LOGGER.debug("Adding server discovery task for squeezebox")
        hass.data[DOMAIN][DISCOVERY_TASK] = hass.async_create_task(
            async_discover(_discovered_server)
        )


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Logitech Squeezebox component."""
    if hass.is_running:
        await start_server_discovery(hass)
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, start_server_discovery(hass)
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Logitech Squeezebox from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    # Stop server discovery task if this is the last config entry.
    current_entries = hass.config_entries.async_entries(DOMAIN)
    if len(current_entries) == 1 and current_entries[0] == entry:
        _LOGGER.debug("Stopping server discovery task")
        hass.data[DOMAIN][DISCOVERY_TASK].cancel()

    return await hass.config_entries.async_forward_entry_unload(entry, MP_DOMAIN)
