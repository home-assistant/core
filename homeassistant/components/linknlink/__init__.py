"""The linknlink integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, get_domains
from .coordinator import LinknLinkCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a linknlink device from a config entry."""
    coordinator = LinknLinkCoordinator(hass, entry.data[CONF_MAC])
    if not await coordinator.async_setup():
        _LOGGER.error(
            "Unable to setup linknlink device - config=%s",
            coordinator.config_entry.data,
        )
        raise ConfigEntryNotReady

    unlisten = entry.add_update_listener(async_update)
    entry.async_on_unload(unlisten)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    # Forward entry setup to related domains.
    await hass.config_entries.async_forward_entry_setups(
        entry, get_domains(coordinator.api.type)
    )

    return True


async def async_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: LinknLinkCoordinator = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, get_domains(device.api.type)
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
