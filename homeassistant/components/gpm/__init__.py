"""The GPM integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from ._manager import (
    IntegrationRepositoryManager,
    RepositoryManager,
    RepositoryType,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from .const import (
    CONF_DOWNLOAD_URL,
    CONF_UPDATE_STRATEGY,
    DOMAIN,
    PATH_RESOURCE_INSTALL_BASEDIR,
    URL_BASE,
)

PLATFORMS: list[Platform] = [Platform.UPDATE]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type GPMConfigEntry = ConfigEntry[RepositoryManager]  # noqa: F821

_LOGGER = logging.getLogger(__name__)


def get_manager(hass: HomeAssistant, data: Mapping[str, str]) -> RepositoryManager:
    """Get the RepositoryManager from a config entry or ConfigFlow.user_input data."""
    # explicitly cast type to trigger fail in case of unexpected data
    if RepositoryType(data[CONF_TYPE]) == RepositoryType.INTEGRATION:
        return IntegrationRepositoryManager(
            hass, data[CONF_URL], UpdateStrategy(data[CONF_UPDATE_STRATEGY])
        )
    return ResourceRepositoryManager(
        hass,
        data[CONF_URL],
        UpdateStrategy(data[CONF_UPDATE_STRATEGY]),
        data[CONF_DOWNLOAD_URL],
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GPM integration."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, hass.config.path(PATH_RESOURCE_INSTALL_BASEDIR))]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Set up GPM from a config entry."""
    manager = get_manager(hass, entry.data)
    if not await manager.is_installed():
        raise ConfigEntryError(
            f"Repository `{entry.data[CONF_URL]}` is not installed despite existing config entry"
        )
    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: GPMConfigEntry) -> None:
    """Remove a config entry."""
    # recreate the manager temporarily because to ConfigEntry.async_unload deletes runtime_data
    manager = get_manager(hass, entry.data)
    await manager.remove()
