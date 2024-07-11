"""Support for Azure DevOps sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from aioazuredevops.models.builds import Build

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import AzureDevOpsConfigEntry
from .coordinator import AzureDevOpsDataUpdateCoordinator
from .entity import AzureDevOpsEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsBuildSensorEntityDescription(SensorEntityDescription):
    """Class describing Azure DevOps base build sensor entities."""

    attr_fn: Callable[[Build], dict[str, Any] | None] = lambda _: None
    value_fn: Callable[[Build], datetime | StateType]


BASE_BUILD_SENSOR_DESCRIPTIONS: tuple[AzureDevOpsBuildSensorEntityDescription, ...] = (
    # Attributes are deprecated in 2024.7 and can be removed in 2025.1
    AzureDevOpsBuildSensorEntityDescription(
        key="latest_build",
        translation_key="latest_build",
        attr_fn=lambda build: {
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
        value_fn=lambda build: build.build_number,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="build_id",
        translation_key="build_id",
        entity_registry_visible_default=False,
        value_fn=lambda build: build.build_id,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="reason",
        translation_key="reason",
        entity_registry_visible_default=False,
        value_fn=lambda build: build.reason,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="result",
        translation_key="result",
        entity_registry_visible_default=False,
        value_fn=lambda build: build.result,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="source_branch",
        translation_key="source_branch",
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
        value_fn=lambda build: build.source_branch,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="source_version",
        translation_key="source_version",
        entity_registry_visible_default=False,
        value_fn=lambda build: build.source_version,
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="queue_time",
        translation_key="queue_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
        value_fn=lambda build: parse_datetime(build.queue_time),
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="start_time",
        translation_key="start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_visible_default=False,
        value_fn=lambda build: parse_datetime(build.start_time),
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="finish_time",
        translation_key="finish_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_visible_default=False,
        value_fn=lambda build: parse_datetime(build.finish_time),
    ),
    AzureDevOpsBuildSensorEntityDescription(
        key="url",
        translation_key="url",
        value_fn=lambda build: build.links.web if build.links else None,
    ),
)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse datetime string."""
    if value is None:
        return None

    return dt_util.parse_datetime(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzureDevOpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    coordinator = entry.runtime_data
    initial_builds: list[Build] = coordinator.data.builds

    async_add_entities(
        AzureDevOpsBuildSensor(
            coordinator,
            description,
            key,
        )
        for description in BASE_BUILD_SENSOR_DESCRIPTIONS
        for key, build in enumerate(initial_builds)
        if build.project and build.definition
    )


class AzureDevOpsBuildSensor(AzureDevOpsEntity, SensorEntity):
    """Define a Azure DevOps build sensor."""

    entity_description: AzureDevOpsBuildSensorEntityDescription

    def __init__(
        self,
        coordinator: AzureDevOpsDataUpdateCoordinator,
        description: AzureDevOpsBuildSensorEntityDescription,
        item_key: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self.item_key = item_key
        self._attr_unique_id = (
            f"{self.coordinator.data.organization}_"
            f"{self.build.project.id}_"
            f"{self.build.definition.build_id}_"
            f"{description.key}"
        )
        self._attr_translation_placeholders = {
            "definition_name": self.build.definition.name
        }

    @property
    def build(self) -> Build:
        """Return the build."""
        return self.coordinator.data.builds[self.item_key]

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.build)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""
        return self.entity_description.attr_fn(self.build)
