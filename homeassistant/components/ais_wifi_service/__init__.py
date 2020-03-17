"""
Support for AIS WiFI connection.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com
"""
import logging
import asyncio
from .config_flow import configured_connections


_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the AIS WiFI connection."""
    _LOGGER.info("async_setup AIS WiFI connection .")

    # info about discovery
    async def do_the_ais_wifi_disco(service):
        """ Called when a AIS WiFi integration has been discovered. """
        await hass.config_entries.flow.async_init(
            "ais_wifi_service", context={"source": "discovery"}, data={}
        )
        await hass.async_block_till_done()

    # hass.async_add_job(do_the_ais_wifi_disco(hass))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up drive as wifi sensor  config entry."""
    _LOGGER.info("Set up wifi sensor as config entry")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True
