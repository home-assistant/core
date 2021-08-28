"""Support for Azure DevOps."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.client import DevOpsClient
from aioazuredevops.core import DevOpsProject
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_ORG, CONF_PAT, CONF_PROJECT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

BUILDS_QUERY: Final = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"


@dataclass
class AzureDevOpsEntityDescription(EntityDescription):
    """Class describing Azure DevOps entities."""

    organization: str = ""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""
    client: DevOpsClient = DevOpsClient()

    if entry.data[CONF_PAT] is not None:
        await client.authorize(entry.data[CONF_PAT], entry.data[CONF_ORG])
        if not client.authorized:
            raise ConfigEntryAuthFailed(
                "Could not authorize with Azure DevOps. You will need to update your token"
            )

    async def async_update_data() -> tuple[
        DevOpsClient, DevOpsProject, list[DevOpsBuild]
    ]:
        """Fetch data from Azure DevOps."""

        try:
            project, builds = await asyncio.gather(
                client.get_project(
                    entry.data[CONF_ORG],
                    entry.data[CONF_PROJECT],
                ),
                client.get_builds(
                    entry.data[CONF_ORG],
                    entry.data[CONF_PROJECT],
                    BUILDS_QUERY,
                ),
            )
            return client, project, builds
        except (aiohttp.ClientError, aiohttp.ClientError) as exception:
            raise UpdateFailed from exception

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=f"{DOMAIN}_coordinator",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=300),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azure DevOps config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


class AzureDevOpsEntity(CoordinatorEntity):
    """Defines a base Azure DevOps entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: AzureDevOpsEntityDescription,
    ) -> None:
        """Initialize the Azure DevOps entity."""
        super().__init__(coordinator)
        _, project, _ = coordinator.data
        self.project = project.name
        self.organization = description.organization


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
