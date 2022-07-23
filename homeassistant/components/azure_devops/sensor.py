"""Support for Azure DevOps sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.work_item import DevOpsWorkItemValue

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AzureDevOpsDeviceEntity, AzureDevOpsEntityDescription
from .const import CONF_ORG, DOMAIN


@dataclass
class AzureDevOpsBuildSensorEntityDescriptionMixin:
    """Mixin class for required Azure DevOps build sensor description keys."""

    item_key: int


@dataclass
class AzureDevOpsWorkItemSensorEntityDescriptionMixin:
    """Mixin class for required Azure DevOps work item sensor description keys."""

    item_key: str


@dataclass
class AzureDevOpsBuildSensorEntityDescription(
    AzureDevOpsEntityDescription,
    SensorEntityDescription,
    AzureDevOpsBuildSensorEntityDescriptionMixin,
):
    """Class describing Azure DevOps build sensor entities."""

    attrs: Callable[[DevOpsBuild], Any] = round
    value: Callable[[DevOpsBuild], StateType] = round


@dataclass
class AzureDevOpsWorkItemSensorEntityDescription(
    AzureDevOpsEntityDescription,
    SensorEntityDescription,
    AzureDevOpsWorkItemSensorEntityDescriptionMixin,
):
    """Class describing Azure DevOps work item sensor entities."""

    value: Callable[[Any, Any], StateType] = round


def filter_work_items_by_type(
    work_items: list[DevOpsWorkItemValue],
    work_item_type: str,
) -> list[DevOpsWorkItemValue]:
    """Filter work items by type."""
    return [item for item in work_items if item.fields.work_item_type == work_item_type]


def build_sensor_attributes(build: DevOpsBuild) -> dict:
    """Build sensor attributes."""
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


def work_item_sensor_value(
    work_items: list[DevOpsWorkItemValue], work_item_type: str
) -> StateType:
    """Return the value of a work item sensor."""
    return len(filter_work_items_by_type(work_items, work_item_type))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator, project = hass.data[DOMAIN][entry.entry_id]
    [builds, wis] = coordinator.data

    sensors: list[AzureDevOpsSensor] = []
    sensors.extend(
        [
            AzureDevOpsBuildSensor(
                coordinator,
                AzureDevOpsBuildSensorEntityDescription(
                    key=f"{project.id}_{build.definition.id}_latest_build",
                    name=f"{project.name} {build.definition.name} Latest Build",
                    icon="mdi:pipe",
                    attrs=build_sensor_attributes,
                    item_key=key,
                    organization=entry.data[CONF_ORG],
                    project=project,
                    value=lambda build: build.build_number,
                ),
            )
            for key, build in enumerate(builds)
        ]
    )
    if wis is not None:
        sensors.append(
            AzureDevOpsWorkItemSensor(
                coordinator,
                AzureDevOpsWorkItemSensorEntityDescription(
                    key=f"{project.id}_work_items",
                    name=f"{project.name} Work Items",
                    icon="mdi:file-tree",
                    item_key="",
                    organization=entry.data[CONF_ORG],
                    project=project,
                    value=lambda work_items, _: len(work_items),
                ),
            ),
        )
        sensors.extend(
            [
                AzureDevOpsWorkItemSensor(
                    coordinator,
                    AzureDevOpsWorkItemSensorEntityDescription(
                        key=f"{project.id}_type_{work_item_type}_work_items",
                        name=f"{project.name} {work_item_type} Items",
                        icon="mdi:file-tree",
                        item_key=work_item_type,
                        organization=entry.data[CONF_ORG],
                        project=project,
                        value=work_item_sensor_value,
                    ),
                )
                for work_item_type in list({wi.fields.work_item_type: wi for wi in wis})
            ]
        )

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Define a Azure DevOps sensor."""

    entity_description: AzureDevOpsBuildSensorEntityDescription | AzureDevOpsWorkItemSensorEntityDescription


class AzureDevOpsBuildSensor(AzureDevOpsSensor):
    """Define a Azure DevOps build sensor."""

    entity_description: AzureDevOpsBuildSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        [builds, _] = self.coordinator.data
        return self.entity_description.value(builds[self.entity_description.item_key])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        [builds, _] = self.coordinator.data
        return self.entity_description.attrs(builds[self.entity_description.item_key])


class AzureDevOpsWorkItemSensor(AzureDevOpsSensor):
    """Define a Azure DevOps work item sensor."""

    entity_description: AzureDevOpsWorkItemSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        [_, work_items] = self.coordinator.data
        return self.entity_description.value(
            work_items, self.entity_description.item_key
        )
