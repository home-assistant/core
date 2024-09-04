"""The GPM integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_create_issue

from ._manager import RepositoryManager, RepositoryType, UpdateStrategy
from .const import CONF_UPDATE_STRATEGY, PATH_CLONE_BASEDIR, PATH_INSTALL_BASEDIR
from .repairs import create_restart_issue

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
    manager = entry.runtime_data
    create_restart_issue(
        async_create_issue,
        hass,
        action="uninstall",
        component_name=manager.component_name,
    )
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> None:
    """Remove a config entry."""
    # recreate the manager temporarily because to ConfigEntry.async_unload deletes runtime_data
    manager = _get_manager(hass, entry)
    await hass.async_add_executor_job(manager.remove)
