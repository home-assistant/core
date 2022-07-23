"""Support for Azure DevOps."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from aioazuredevops.client import DevOpsClient
from aioazuredevops.core import DevOpsProject

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import AzureDevOpsCoordinatorData, AzureDevOpsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class AzureDevOpsEntityDescription(EntityDescription):
    """Class describing Azure DevOps entities."""

    organization: str = ""
    project: DevOpsProject = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""
    client = DevOpsClient()

    coordinator = AzureDevOpsDataUpdateCoordinator(
        hass,
        _LOGGER,
        entry=entry,
        client=client,
    )

    await coordinator.authorize()
    project: DevOpsProject = await coordinator.get_project()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator, project

    # Update data for the first time
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azure DevOps config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


class AzureDevOpsEntity(
    CoordinatorEntity[DataUpdateCoordinator[AzureDevOpsCoordinatorData]]
):
    """Defines a base Azure DevOps entity."""

    entity_description: AzureDevOpsEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[AzureDevOpsCoordinatorData],
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
