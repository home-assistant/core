"""The awair component."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    AwairCloudDataUpdateCoordinator,
    AwairConfigEntry,
    AwairDataUpdateCoordinator,
    AwairLocalDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: AwairConfigEntry
) -> None:
    """Set up Awair integration from a config entry."""
    session = async_get_clientsession(hass)

    coordinator: AwairDataUpdateCoordinator

    if CONF_HOST in config_entry.data:
        coordinator = AwairLocalDataUpdateCoordinator(hass, config_entry, session)
    else:
        coordinator = AwairCloudDataUpdateCoordinator(hass, config_entry, session)

    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    if CONF_HOST in config_entry.data:
        config_entry.async_on_unload(
            config_entry.add_update_listener(_async_update_listener)
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: AwairConfigEntry) -> None:
    """Reload when the title or the host changed."""
    coordinator = entry.runtime_data
    if entry.title != coordinator.title or entry.data[CONF_HOST] != coordinator.host:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: AwairConfigEntry
) -> None:
    """Unload Awair configuration."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
