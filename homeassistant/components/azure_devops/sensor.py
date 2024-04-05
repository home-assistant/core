"""Support for Azure DevOps sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from aioazuredevops.builds import DevOpsBuild

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AzureDevOpsDeviceEntity, AzureDevOpsEntityDescription
from .const import CONF_ORG, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsSensorEntityDescription(
    AzureDevOpsEntityDescription, SensorEntityDescription
):
    """Class describing Azure DevOps sensor entities."""

    build_key: int
    attrs: Callable[[DevOpsBuild], dict[str, Any]] | None
    value: Callable[[DevOpsBuild], StateType]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator, project = hass.data[DOMAIN][entry.entry_id]
    initial_data: list[DevOpsBuild] = coordinator.data

    sensors: list[AzureDevOpsSensor] = []

    for key, build in enumerate(initial_data):
        if build.project is None or build.definition is None:
            _LOGGER.warning(
                "Skipping build %s as it is missing project or definition: %s",
                key,
                build,
            )
            continue

        build_sensor_key_base = (
            f"{build.project.project_id}_{build.definition.build_id}"
        )

        descriptions: list[AzureDevOpsSensorEntityDescription] = [
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_latest_build",
                translation_key="latest_build",
                translation_placeholders={"definition_name": build.definition.name},
                attrs=lambda build: {
                    "definition_id": (
                        build.definition.build_id if build.definition else None
                    ),
                    "definition_name": (
                        build.definition.name if build.definition else None
                    ),
                    "id": build.build_id,
                    "reason": build.reason,
                    "result": build.result,
                    "source_branch": build.source_branch,
                    "source_version": build.source_version,
                    "status": build.status,
                    "url": build.links.web if build.links else None,
                    "queue_time": build.queue_time,
                    "start_time": build.start_time,
                    "finish_time": build.finish_time,
                },
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.build_number,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_definition_id",
                translation_key="definition_id",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_enabled_default=False,
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: (
                    build.definition.build_id if build.definition else None
                ),
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_definition_name",
                translation_key="definition_name",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_enabled_default=False,
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: (
                    build.definition.name if build.definition else None
                ),
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_build_id",
                translation_key="build_id",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.build_id,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_reason",
                translation_key="reason",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.reason,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_result",
                translation_key="result",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.result,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_source_branch",
                translation_key="source_branch",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_enabled_default=False,
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.source_branch,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_source_version",
                translation_key="source_version",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.source_version,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_queue_time",
                translation_key="queue_time",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_enabled_default=False,
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.queue_time,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_start_time",
                translation_key="start_time",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.start_time,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_finish_time",
                translation_key="finish_time",
                translation_placeholders={"definition_name": build.definition.name},
                entity_registry_visible_default=False,
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.finish_time,
            ),
            AzureDevOpsSensorEntityDescription(
                key=f"{build_sensor_key_base}_url",
                translation_key="url",
                translation_placeholders={"definition_name": build.definition.name},
                attrs=None,
                build_key=key,
                organization=entry.data[CONF_ORG],
                project=project,
                value=lambda build: build.links.web if build.links else None,
            ),
        ]

        sensors.extend(
            AzureDevOpsSensor(
                coordinator,
                description,
            )
            for description in descriptions
        )

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
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""
        if self.entity_description.attrs is None:
            return None

        build: DevOpsBuild = self.coordinator.data[self.entity_description.build_key]
        return self.entity_description.attrs(build)
