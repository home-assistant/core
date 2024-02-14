"""Support for Azure DevOps."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.client import DevOpsClient
from aioazuredevops.core import DevOpsProject
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_ORG, CONF_PAT, CONF_PROJECT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

BUILDS_QUERY: Final = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"


@dataclass(frozen=True)
class AzureDevOpsEntityDescription(EntityDescription):
    """Class describing Azure DevOps entities."""

    organization: str = ""
    project: DevOpsProject = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""
    client = DevOpsClient()

    if entry.data.get(CONF_PAT) is not None:
        await client.authorize(entry.data[CONF_PAT], entry.data[CONF_ORG])
        if not client.authorized:
            raise ConfigEntryAuthFailed(
                "Could not authorize with Azure DevOps. You will need to update your"
                " token"
            )

    project = await client.get_project(
        entry.data[CONF_ORG],
        entry.data[CONF_PROJECT],
    )

    async def async_update_data() -> list[DevOpsBuild]:
        """Fetch data from Azure DevOps."""

        try:
            return await client.get_builds(
                entry.data[CONF_ORG],
                entry.data[CONF_PROJECT],
                BUILDS_QUERY,
            )
        except aiohttp.ClientError as exception:
            raise UpdateFailed from exception

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=async_update_data,
        update_interval=timedelta(seconds=300),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator, project

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azure DevOps config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


class AzureDevOpsEntity(CoordinatorEntity[DataUpdateCoordinator[list[DevOpsBuild]]]):
    """Defines a base Azure DevOps entity."""

    entity_description: AzureDevOpsEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[DevOpsBuild]],
        entity_description: AzureDevOpsEntityDescription,
    ) -> None:
        """Initialize the Azure DevOps entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id: str = "_".join(
            [entity_description.organization, entity_description.key]
        )
        self._organization: str = entity_description.organization
        self._project_name: str = entity_description.project.name


class AzureDevOpsDeviceEntity(AzureDevOpsEntity):
    """Defines a Azure DevOps device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Azure DevOps instance."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._organization, self._project_name)},  # type: ignore[arg-type]
            manufacturer=self._organization,
            name=self._project_name,
        )
