"""The Z-Wave JS integration."""
import asyncio
import logging

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Z-Wave JS component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Z-Wave JS from a config entry."""

    # The ZwaveClient instance is stored in hass data for easy access from platforms.
    client = ZwaveClient(entry.data[CONF_ADDRESS], async_get_clientsession(hass))
    hass.data[DOMAIN][entry.entry_id] = client

    async def async_on_initialized():
        """Called when initial full state received."""
        # TODO: signal entities to update availability state
        LOGGER.info("Connection to Zwave JS Server initialized")
        # register callbacks
        client.driver.on("all nodes ready", async_on_ready)

    async def async_on_disconnect():
        """Called when websocket is disconnected."""
        LOGGER.info("Disconnected from Zwave JS Server")
        # TODO: signal entities to update availability state

    async def async_on_ready():
        """Called when Z-wave mesh is ready to handle commands."""
        LOGGER.info("Z-Wave mesh is fully functional.")
        # TODO: signal entities to update availability state

    # register main event callbacks.
    client.register_on_initialized(async_on_initialized)
    client.register_on_disconnect(async_on_disconnect)
    asyncio.create_task(client.connect())

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
