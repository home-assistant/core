"""Support for Azure DevOps sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from aioazuredevops.builds import DevOpsBuild

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import AzureDevOpsDeviceEntity, AzureDevOpsEntityDescription
from .const import CONF_ORG, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsBaseBuildSensorEntityDescription(SensorEntityDescription):
    """Class describing Azure DevOps base build sensor entities."""

    attrs: Callable[[DevOpsBuild], dict[str, Any]] | None
    value: Callable[[DevOpsBuild], datetime | StateType]


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsBuildSensorEntityDescription(
    AzureDevOpsEntityDescription,
    AzureDevOpsBaseBuildSensorEntityDescription,
):
    """Class describing Azure DevOps build sensor entities."""

    item_key: int = 0


BASE_BUILD_SENSOR_DESCRIPTIONS: tuple[
    AzureDevOpsBaseBuildSensorEntityDescription, ...
] = (
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="latest_build",
        translation_key="latest_build",
        attrs=lambda build: {
            "definition_id": (build.definition.build_id if build.definition else None),
            "definition_name": (build.definition.name if build.definition else None),
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
        value=lambda build: build.build_number,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="build_id",
        translation_key="build_id",
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.build_id,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="reason",
        translation_key="reason",
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.reason,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="result",
        translation_key="result",
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.result,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="source_branch",
        translation_key="source_branch",
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.source_branch,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="source_version",
        translation_key="source_version",
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.source_version,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="status",
        translation_key="status",
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: build.status,
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="queue_time",
        translation_key="queue_time",
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: parse_datetime(build.queue_time),
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="start_time",
        translation_key="start_time",
        device_class=SensorDeviceClass.DATE,
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: parse_datetime(build.start_time),
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="finish_time",
        translation_key="finish_time",
        device_class=SensorDeviceClass.DATE,
        entity_registry_visible_default=False,
        attrs=None,
        value=lambda build: parse_datetime(build.finish_time),
    ),
    AzureDevOpsBaseBuildSensorEntityDescription(
        key="url",
        translation_key="url",
        attrs=None,
        value=lambda build: build.links.web if build.links else None,
    ),
)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse datetime string."""
    if value is None:
        return None

    return dt_util.parse_datetime(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator, project = hass.data[DOMAIN][entry.entry_id]
    initial_builds: list[DevOpsBuild] = coordinator.data

    sensors: list[AzureDevOpsBuildSensor] = []

    # Add build sensors
    for key, build in enumerate(initial_builds):
        if build.project is None or build.definition is None:
            _LOGGER.warning(
                "Skipping build %s as it is missing a project or definition: %s",
                key,
                build,
            )
            continue

        build_sensor_key_base = (
            f"{build.project.project_id}_{build.definition.build_id}"
        )

        descriptions: list[AzureDevOpsBuildSensorEntityDescription] = [
            AzureDevOpsBuildSensorEntityDescription(
                key=f"{build_sensor_key_base}_{description.key}",
                translation_key=description.translation_key,
                translation_placeholders={"definition_name": build.definition.name},
                device_class=description.device_class,
                entity_registry_enabled_default=description.entity_registry_enabled_default,
                entity_registry_visible_default=description.entity_registry_visible_default,
                organization=entry.data[CONF_ORG],
                project=project,
                item_key=key,
                attrs=description.attrs,
                value=description.value,
            )
            for description in BASE_BUILD_SENSOR_DESCRIPTIONS
        ]

        sensors.extend(
            AzureDevOpsBuildSensor(
                coordinator,
                description,
            )
            for description in descriptions
        )

    async_add_entities(sensors, True)


class AzureDevOpsBuildSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Define a Azure DevOps build sensor."""

    entity_description: AzureDevOpsBuildSensorEntityDescription

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state."""
        return self.entity_description.value(
            self.coordinator.data[self.entity_description.item_key]
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""
        if self.entity_description.attrs is None:
            return None

        return self.entity_description.attrs(
            self.coordinator.data[self.entity_description.item_key]
        )
