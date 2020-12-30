"""Support for AI-Speaker."""
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ai_speaker"


async def async_setup(hass, config):
    """Set up the initial domain configuration - currently not necessary."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the integration based on a configuration entry."""
    _LOGGER.debug("async_setup_entry " + str(config_entry))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry - delete configuration entities."""
    _LOGGER.debug("async_unload_entry remove entities")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    )
    return True
