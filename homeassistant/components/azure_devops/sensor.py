"""Support for Azure DevOps sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aioazuredevops.builds import DevOpsBuild

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AzureDevOpsDeviceEntity, AzureDevOpsEntityDescription
from .const import CONF_ORG, DOMAIN


@dataclass
class AzureDevOpsSensorEntityDescriptionMixin:
    """Mixin class for required Azure DevOps sensor description keys."""

    build_key: int


@dataclass
class AzureDevOpsSensorEntityDescription(
    AzureDevOpsEntityDescription,
    SensorEntityDescription,
    AzureDevOpsSensorEntityDescriptionMixin,
):
    """Class describing Azure DevOps sensor entities."""

    attrs: Callable[[DevOpsBuild], Any] = round
    value: Callable[[DevOpsBuild], StateType] = round


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator, project = hass.data[DOMAIN][entry.entry_id]

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
                project=project,
                value=lambda build: build.build_number,
            ),
        )
        for key, build in enumerate(coordinator.data)
    ]

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Define a Azure DevOps sensor."""

    entity_description: AzureDevOpsSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        build: DevOpsBuild = self.coordinator.data[self.entity_description.build_key]
        return self.entity_description.value(build)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        build: DevOpsBuild = self.coordinator.data[self.entity_description.build_key]
        return self.entity_description.attrs(build)
