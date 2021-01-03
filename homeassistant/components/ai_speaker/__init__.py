"""Support for AI-Speaker."""
import logging

from aisapi.ws import AisWebService

from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

PLATFORMS = ["sensor", "media_player"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the initial domain configuration."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the integration based on a configuration entry."""
    _LOGGER.debug("async_setup_entry %s", config_entry)
    web_session = aiohttp_client.async_get_clientsession(hass)
    ais_url = config_entry.data.get("ais_info")["ais_url"]
    ais_gate = AisWebService(hass.loop, web_session, ais_url)

    async def async_command(service):
        """Publish command to AI-Speaker WS."""
        await ais_gate.command(service.data["key"], service.data["val"])

    hass.services.async_register(DOMAIN, "publish_command", async_command)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry - delete configuration entities."""
    _LOGGER.debug("async_unload_entry remove entities")
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(config_entry, component)
        )
    return True
