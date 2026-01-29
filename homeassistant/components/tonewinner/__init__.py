"""Set up Tonewinner from a config entry."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Tonewinner integration module loaded!")


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Options updated for entry %s, reloading integration", entry.entry_id)
    _LOGGER.debug("Current entry data: %s", entry.data)
    _LOGGER.debug("Current entry options: %s", entry.options)
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug("Integration reload initiated for entry %s", entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tonewinner from a config entry."""
    _LOGGER.debug("Setting up Tonewinner integration for entry: %s", entry.entry_id)
    _LOGGER.debug("Entry data: %s", entry.data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Pass a LIST of platforms
    _LOGGER.debug("Forwarding entry setup to media_player platform")
    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Tonewinner integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Tonewinner integration for entry: %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_unload(entry, "media_player")

    # Unregister the service if it exists
    service_key = f"{entry.entry_id}_service"
    if service_key in hass.data[DOMAIN]:
        _LOGGER.debug("Unregistering service")
        hass.services.async_remove(DOMAIN, "send_raw")
        del hass.data[DOMAIN][service_key]

    hass.data[DOMAIN].pop(entry.entry_id)
    _LOGGER.info("Tonewinner integration unloaded")
    return True
