"""The GPM integration."""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_create_issue

from ._manager import (
    IntegrationRepositoryManager,
    RepositoryManager,
    RepositoryType,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from .const import (
    CONF_UPDATE_STRATEGY,
    PATH_CLONE_BASEDIR,
    PATH_INTEGRATION_INSTALL_BASEDIR,
    PATH_RESOURCE_INSTALL_BASEDIR,
)
from .repairs import create_restart_issue

PLATFORMS: list[Platform] = [Platform.UPDATE]

type GPMConfigEntry = ConfigEntry[RepositoryManager]  # noqa: F821


def get_manager(hass: HomeAssistant, data: Mapping[str, str]) -> RepositoryManager:
    """Get the RepositoryManager from a config entry or ConfigFlow.user_input data."""
    # explicitly cast type to trigger fail in case of unexpected data
    type_ = RepositoryType(data[CONF_TYPE])
    if type_ == RepositoryType.INTEGRATION:
        return IntegrationRepositoryManager(
            data[CONF_URL],
            hass.config.path(PATH_CLONE_BASEDIR),
            hass.config.path(PATH_INTEGRATION_INSTALL_BASEDIR),
            UpdateStrategy(data[CONF_UPDATE_STRATEGY]),
        )
    return ResourceRepositoryManager(
        data[CONF_URL],
        hass.config.path(PATH_CLONE_BASEDIR),
        hass.config.path(PATH_RESOURCE_INSTALL_BASEDIR),
        UpdateStrategy(data[CONF_UPDATE_STRATEGY]),
    )


async def async_setup_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Set up GPM from a config entry."""
    entry.runtime_data = get_manager(hass, entry.data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Unload a config entry."""
    manager = entry.runtime_data
    issue_domain = (
        manager.component_name
        if isinstance(manager, IntegrationRepositoryManager)
        else None
    )
    create_restart_issue(
        async_create_issue,
        hass,
        action="uninstall",
        name=manager.slug,
        issue_domain=issue_domain,
    )
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> None:
    """Remove a config entry."""
    # recreate the manager temporarily because to ConfigEntry.async_unload deletes runtime_data
    manager = get_manager(hass, entry.data)
    await hass.async_add_executor_job(manager.remove)
