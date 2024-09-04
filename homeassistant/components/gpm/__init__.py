"""The GPM integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant

from ._manager import RepositoryManager, RepositoryType, UpdateStrategy
from .const import CONF_UPDATE_STRATEGY, PATH_CLONE_BASEDIR, PATH_INSTALL_BASEDIR

PLATFORMS: list[Platform] = [Platform.UPDATE]

type GPMConfigEntry = ConfigEntry[RepositoryManager]  # noqa: F821


def _get_manager(hass: HomeAssistant, entry: GPMConfigEntry) -> RepositoryManager:
    """Get the RepositoryManager from a config entry."""
    return RepositoryManager(
        entry.data[CONF_URL],
        RepositoryType(entry.data[CONF_TYPE]),
        hass.config.path(PATH_CLONE_BASEDIR),
        hass.config.path(PATH_INSTALL_BASEDIR),
        UpdateStrategy(entry.data[CONF_UPDATE_STRATEGY]),
    )


async def async_setup_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Set up GPM from a config entry."""
    entry.runtime_data = _get_manager(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> None:
    """Remove a config entry."""
    # recreate the manager temporarily because to ConfigEntry.async_unload deletes runtime_data
    manager = _get_manager(hass, entry)
    await hass.async_add_executor_job(manager.remove)
