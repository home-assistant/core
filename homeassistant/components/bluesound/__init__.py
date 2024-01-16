"""The bluesound component."""
import logging

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, PLATFORMS

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = []

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluesound from a config entry."""
    _LOGGER.debug("Bluesound async_setup_entry: %s: %r", entry.entry_id, entry.data)

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Bluesound config entry."""
    _LOGGER.debug("Bluesound async_unload_entry with %s: %r", entry.entry_id, entry.data)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # TODO(trainman419): does this work on a list? Will it unload the player?
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok