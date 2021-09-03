"""Support for Azure DevOps sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from aioazuredevops.builds import DevOpsBuild

from homeassistant.components.azure_devops import (
    AzureDevOpsDeviceEntity,
    AzureDevOpsEntityDescription,
)
from homeassistant.components.azure_devops.const import CONF_ORG, DOMAIN
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class AzureDevOpsSensorEntityDescription(
    AzureDevOpsEntityDescription, SensorEntityDescription
):
    """Class describing Azure DevOps sensor entities."""

    attrs: Callable[[DevOpsBuild], Any] = round
    build_key: int | None = None
    value: Callable[[DevOpsBuild], StateType] = round


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    _, builds = coordinator.data

    sensors = [
        AzureDevOpsSensor(
            coordinator,
            AzureDevOpsSensorEntityDescription(
                key=f"{build.project.id}_{build.definition.id}_latest_build",
                name=f"{build.project.name} {build.definition.name} Latest Build",
                icon="mdi:pipe",
                attrs=lambda build: {
                    "definition_id": build.definition.id,
                    "definition_name": build.definition.name,
                    "id": build.id,
                    "reason": build.reason,
                    "result": build.result,
                    "source_branch": build.source_branch,
                    "source_version": build.source_version,
                    "status": build.status,
                    "url": build.links.web,
                    "queue_time": build.queue_time,
                    "start_time": build.start_time,
                    "finish_time": build.finish_time,
                },
                build_key=key,
                organization=entry.data[CONF_ORG],
                value=lambda build: build.build_number,
            ),
        )
        for key, build in enumerate(builds)
    ]

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Define a Azure DevOps sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: AzureDevOpsSensorEntityDescription,
    ) -> None:
        """Initialize Azure DevOps sensor."""
        self._attr_unique_id = "_".join([description.organization, description.key])
        self.entity_description: AzureDevOpsSensorEntityDescription = description
        super().__init__(
            coordinator,
            description,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        _, builds = self.coordinator.data
        build: DevOpsBuild = builds[self.entity_description.build_key]
        return self.entity_description.value(build)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        _, builds = self.coordinator.data
        build: DevOpsBuild = builds[self.entity_description.build_key]
        return self.entity_description.attrs(build)
