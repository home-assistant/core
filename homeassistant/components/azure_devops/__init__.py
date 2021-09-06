"""Support for Azure DevOps."""
from __future__ import annotations

import logging

from aioazuredevops.client import DevOpsClient
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_ORG, CONF_PAT, CONF_PROJECT, DATA_AZURE_DEVOPS_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""
    client = DevOpsClient()

    try:
        if entry.data[CONF_PAT] is not None:
            await client.authorize(entry.data[CONF_PAT], entry.data[CONF_ORG])
            if not client.authorized:
                raise ConfigEntryAuthFailed(
                    "Could not authorize with Azure DevOps. You may need to update your token"
                )
        await client.get_project(entry.data[CONF_ORG], entry.data[CONF_PROJECT])
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise ConfigEntryNotReady from exception

    instance_key = f"{DOMAIN}_{entry.data[CONF_ORG]}_{entry.data[CONF_PROJECT]}"
    hass.data.setdefault(instance_key, {})[DATA_AZURE_DEVOPS_CLIENT] = client

    # Setup components
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azure DevOps config entry."""
    del hass.data[f"{DOMAIN}_{entry.data[CONF_ORG]}_{entry.data[CONF_PROJECT]}"]

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class AzureDevOpsEntity(Entity):
    """Defines a base Azure DevOps entity."""

    def __init__(self, organization: str, project: str, name: str, icon: str) -> None:
        """Initialize the Azure DevOps entity."""
        self._attr_name = name
        self._attr_icon = icon
        self.organization = organization
        self.project = project

    async def async_update(self) -> None:
        """Update Azure DevOps entity."""
        if await self._azure_devops_update():
            self._attr_available = True
        else:
            if self._attr_available:
                _LOGGER.debug(
                    "An error occurred while updating Azure DevOps sensor",
                    exc_info=True,
                )
            self._attr_available = False

    async def _azure_devops_update(self) -> bool:
        """Update Azure DevOps entity."""
        raise NotImplementedError()


class AzureDevOpsDeviceEntity(AzureDevOpsEntity):
    """Defines a Azure DevOps device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Azure DevOps instance."""
        return {
            "identifiers": {
                (  # type: ignore
                    DOMAIN,
                    self.organization,
                    self.project,
                )
            },
            "manufacturer": self.organization,
            "name": self.project,
            "entry_type": "service",
        }
