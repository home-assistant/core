"""The Noonlight emergency-dispatch integration."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Noonlight integration.

    Domain-level services are registered here so they exist even when no
    config entry is loaded; the handlers resolve the target entry at call time.
    """
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> bool:
    """Set up a Noonlight config entry."""
    coordinator = NoonlightCoordinator(hass, entry)
    await coordinator.async_load()
    # Establish initial data; the first refresh is a no-op while idle.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> bool:
    """Unload a Noonlight config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    await entry.runtime_data.async_shutdown()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
