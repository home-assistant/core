"""Support for AI-Speaker."""
import logging

from homeassistant.helpers import aiohttp_client

from .const import AIS_WS_COMMAND_URL, DOMAIN

PLATFORMS = ["sensor", "media_player"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the initial domain configuration."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the integration based on a configuration entry."""

    _LOGGER.debug("async_setup_entry " + str(config_entry))
    web_session = aiohttp_client.async_get_clientsession(hass)

    async def async_command(service):
        """Publish command to AI-Speaker WS."""
        requests_json = {service.data["key"]: service.data["val"]}
        ais_ws_url = AIS_WS_COMMAND_URL.format(ais_url=service.data["ais_url"])
        try:
            await web_session.post(ais_ws_url, json=requests_json, timeout=3)
        except Exception as e:
            _LOGGER.error("Publish command to AI-Speaker error: " + str(e))

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
