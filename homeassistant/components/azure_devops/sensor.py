"""Support for Azure DevOps sensors."""
from __future__ import annotations

from typing import Any

from aioazuredevops.builds import DevOpsBuild

from homeassistant.components.azure_devops import AzureDevOpsDeviceEntity
from homeassistant.components.azure_devops.const import CONF_ORG, DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    _, _, builds = coordinator.data

    sensors = [
        AzureDevOpsLatestBuildSensor(
            coordinator,
            entry.data[CONF_ORG],
            key,
        )
        for key, _ in enumerate(builds)
    ]

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Defines a Azure DevOps sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        organization: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize Azure DevOps sensor."""
        super().__init__(coordinator, organization, key, name, icon)


class AzureDevOpsLatestBuildSensor(AzureDevOpsSensor):
    """Defines a Azure DevOps card count sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        organization: str,
        key: int,
    ) -> None:
        """Initialize Azure DevOps sensor."""
        _, _, builds = coordinator.data
        build: DevOpsBuild = builds[key]
        super().__init__(
            coordinator,
            organization,
            f"{build.project.id}_{build.definition.id}_latest_build",
            f"{build.project.name} {build.definition.name} Latest Build",
            "mdi:pipe",
        )
        self._key = key

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        _, _, builds = self.coordinator.data
        build: DevOpsBuild = builds[self._key]
        return build.build_number

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        _, _, builds = self.coordinator.data
        build: DevOpsBuild = builds[self._key]
        return {
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
        }
