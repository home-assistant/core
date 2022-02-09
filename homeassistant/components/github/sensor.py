"""Sensor platform for the GitHub integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    CoordinatorKeyType,
    DataUpdateCoordinators,
    GitHubBaseDataUpdateCoordinator,
)


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required GitHub base description keys."""

    coordinator_key: CoordinatorKeyType
    value_fn: Callable[[Any], StateType]


@dataclass
class BaseEntityDescription(SensorEntityDescription):
    """Describes GitHub sensor entity default overrides."""

    icon: str = "mdi:github"
    entity_registry_enabled_default: bool = False
    attr_fn: Callable[[Any], Mapping[str, Any] | None] = lambda data: None
    avabl_fn: Callable[[Any], bool] = lambda data: True


@dataclass
class GitHubSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describes GitHub issue sensor entity."""


SENSOR_DESCRIPTIONS: tuple[GitHubSensorEntityDescription, ...] = (
    GitHubSensorEntityDescription(
        key="stargazers_count",
        name="Stars",
        icon="mdi:star",
        native_unit_of_measurement="Stars",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stargazers_count,
        coordinator_key="information",
    ),
    GitHubSensorEntityDescription(
        key="subscribers_count",
        name="Watchers",
        icon="mdi:glasses",
        native_unit_of_measurement="Watchers",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        # The API returns a watcher_count, but subscribers_count is more accurate
        value_fn=lambda data: data.subscribers_count,
        coordinator_key="information",
    ),
    GitHubSensorEntityDescription(
        key="forks_count",
        name="Forks",
        icon="mdi:source-fork",
        native_unit_of_measurement="Forks",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.forks_count,
        coordinator_key="information",
    ),
    GitHubSensorEntityDescription(
        key="issues_count",
        name="Issues",
        native_unit_of_measurement="Issues",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.issues_count,
        coordinator_key="issue",
    ),
    GitHubSensorEntityDescription(
        key="pulls_count",
        name="Pull Requests",
        native_unit_of_measurement="Pull Requests",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pulls_count,
        coordinator_key="issue",
    ),
    GitHubSensorEntityDescription(
        coordinator_key="commit",
        key="latest_commit",
        name="Latest Commit",
        value_fn=lambda data: data.commit.message.splitlines()[0][:255],
        attr_fn=lambda data: {
            "sha": data.sha,
            "url": data.html_url,
        },
    ),
    GitHubSensorEntityDescription(
        coordinator_key="release",
        key="latest_release",
        name="Latest Release",
        entity_registry_enabled_default=True,
        value_fn=lambda data: data.name[:255],
        attr_fn=lambda data: {
            "url": data.html_url,
            "tag": data.tag_name,
        },
    ),
    GitHubSensorEntityDescription(
        coordinator_key="issue",
        key="latest_issue",
        name="Latest Issue",
        value_fn=lambda data: data.issue_last.title[:255],
        avabl_fn=lambda data: data.issue_last is not None,
        attr_fn=lambda data: {
            "url": data.issue_last.html_url,
            "number": data.issue_last.number,
        },
    ),
    GitHubSensorEntityDescription(
        coordinator_key="issue",
        key="latest_pull_request",
        name="Latest Pull Request",
        value_fn=lambda data: data.pull_last.title[:255],
        avabl_fn=lambda data: data.pull_last is not None,
        attr_fn=lambda data: {
            "url": data.pull_last.html_url,
            "number": data.pull_last.number,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GitHub sensor based on a config entry."""
    repositories: dict[str, DataUpdateCoordinators] = hass.data[DOMAIN]
    async_add_entities(
        (
            GitHubSensorEntity(coordinators, description)
            for description in SENSOR_DESCRIPTIONS
            for coordinators in repositories.values()
        ),
        update_before_add=True,
    )


class GitHubSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines a GitHub sensor entity."""

    _attr_attribution = "Data provided by the GitHub API"

    coordinator: GitHubBaseDataUpdateCoordinator
    entity_description: GitHubSensorEntityDescription

    def __init__(
        self,
        coordinators: DataUpdateCoordinators,
        entity_description: GitHubSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        coordinator = coordinators[entity_description.coordinator_key]
        _information = coordinators["information"].data

        super().__init__(coordinator=coordinator)

        self.entity_description = entity_description
        self._attr_name = f"{_information.full_name} {entity_description.name}"
        self._attr_unique_id = f"{_information.id}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.repository)},
            name=_information.full_name,
            manufacturer="GitHub",
            configuration_url=f"https://github.com/{coordinator.repository}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.avabl_fn(self.coordinator.data)
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attr_fn(self.coordinator.data)
