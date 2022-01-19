"""Sensor platform for the GitHub integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from aiogithubapi import GitHubRepositoryModel

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

from .const import DOMAIN, IssuesPulls
from .coordinator import (
    CoordinatorKeyType,
    DataUpdateCoordinators,
    GitHubBaseDataUpdateCoordinator,
    RepositoryCommitDataUpdateCoordinator,
    RepositoryIssueDataUpdateCoordinator,
    RepositoryReleaseDataUpdateCoordinator,
)


@dataclass
class GitHubSensorBaseEntityDescriptionMixin:
    """Mixin for required GitHub base description keys."""

    coordinator_key: CoordinatorKeyType


@dataclass
class GitHubSensorInformationEntityDescriptionMixin(
    GitHubSensorBaseEntityDescriptionMixin
):
    """Mixin for required GitHub information description keys."""

    value_fn: Callable[[GitHubRepositoryModel], StateType]


@dataclass
class GitHubSensorIssueEntityDescriptionMixin(GitHubSensorBaseEntityDescriptionMixin):
    """Mixin for required GitHub information description keys."""

    value_fn: Callable[[IssuesPulls], StateType]


@dataclass
class GitHubSensorBaseEntityDescription(SensorEntityDescription):
    """Describes GitHub sensor entity default overrides."""

    icon: str = "mdi:github"
    entity_registry_enabled_default: bool = False


@dataclass
class GitHubSensorInformationEntityDescription(
    GitHubSensorBaseEntityDescription,
    GitHubSensorInformationEntityDescriptionMixin,
):
    """Describes GitHub information sensor entity."""


@dataclass
class GitHubSensorIssueEntityDescription(
    GitHubSensorBaseEntityDescription,
    GitHubSensorIssueEntityDescriptionMixin,
):
    """Describes GitHub issue sensor entity."""


SENSOR_DESCRIPTIONS: tuple[
    GitHubSensorInformationEntityDescription | GitHubSensorIssueEntityDescription,
    ...,
] = (
    GitHubSensorInformationEntityDescription(
        key="stargazers_count",
        name="Stars",
        icon="mdi:star",
        native_unit_of_measurement="Stars",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stargazers_count,
        coordinator_key="information",
    ),
    GitHubSensorInformationEntityDescription(
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
    GitHubSensorInformationEntityDescription(
        key="forks_count",
        name="Forks",
        icon="mdi:source-fork",
        native_unit_of_measurement="Forks",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.forks_count,
        coordinator_key="information",
    ),
    GitHubSensorIssueEntityDescription(
        key="issues_count",
        name="Issues",
        native_unit_of_measurement="Issues",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.issues_count,
        coordinator_key="issue",
    ),
    GitHubSensorIssueEntityDescription(
        key="pulls_count",
        name="Pull Requests",
        native_unit_of_measurement="Pull Requests",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pulls_count,
        coordinator_key="issue",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GitHub sensor based on a config entry."""
    repositories: dict[str, DataUpdateCoordinators] = hass.data[DOMAIN]
    entities: list[GitHubSensorBaseEntity] = []

    for coordinators in repositories.values():
        repository_information = coordinators["information"].data
        entities.extend(
            sensor(coordinators, repository_information)
            for sensor in (
                GitHubSensorLatestCommitEntity,
                GitHubSensorLatestIssueEntity,
                GitHubSensorLatestPullEntity,
                GitHubSensorLatestReleaseEntity,
            )
        )

        entities.extend(
            GitHubSensorDescriptionEntity(
                coordinators, description, repository_information
            )
            for description in SENSOR_DESCRIPTIONS
        )

    async_add_entities(entities)


class GitHubSensorBaseEntity(CoordinatorEntity, SensorEntity):
    """Defines a base GitHub sensor entity."""

    _attr_attribution = "Data provided by the GitHub API"

    coordinator: GitHubBaseDataUpdateCoordinator

    def __init__(
        self,
        coordinator: GitHubBaseDataUpdateCoordinator,
        repository_information: GitHubRepositoryModel,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.repository)},
            name=repository_information.full_name,
            manufacturer="GitHub",
            configuration_url=f"https://github.com/{self.coordinator.repository}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data is not None


class GitHubSensorDescriptionEntity(GitHubSensorBaseEntity):
    """Defines a GitHub sensor entity based on entity descriptions."""

    coordinator: GitHubBaseDataUpdateCoordinator
    entity_description: GitHubSensorInformationEntityDescription | GitHubSensorIssueEntityDescription

    def __init__(
        self,
        coordinators: DataUpdateCoordinators,
        description: GitHubSensorInformationEntityDescription
        | GitHubSensorIssueEntityDescription,
        repository_information: GitHubRepositoryModel,
    ) -> None:
        """Initialize a GitHub sensor entity."""
        super().__init__(
            coordinator=coordinators[description.coordinator_key],
            repository_information=repository_information,
        )
        self.entity_description = description
        self._attr_name = f"{repository_information.full_name} {description.name}"
        self._attr_unique_id = f"{repository_information.id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class GitHubSensorLatestBaseEntity(GitHubSensorBaseEntity):
    """Defines a base GitHub latest sensor entity."""

    _name: str = "Latest"
    _coordinator_key: CoordinatorKeyType = "information"
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:github"

    def __init__(
        self,
        coordinators: DataUpdateCoordinators,
        repository_information: GitHubRepositoryModel,
    ) -> None:
        """Initialize a GitHub sensor entity."""
        super().__init__(
            coordinator=coordinators[self._coordinator_key],
            repository_information=repository_information,
        )
        self._attr_name = f"{repository_information.full_name} {self._name}"
        self._attr_unique_id = (
            f"{repository_information.id}_{self._name.lower().replace(' ', '_')}"
        )


class GitHubSensorLatestReleaseEntity(GitHubSensorLatestBaseEntity):
    """Defines a GitHub latest release sensor entity."""

    _coordinator_key: CoordinatorKeyType = "release"
    _name: str = "Latest Release"

    _attr_entity_registry_enabled_default = True

    coordinator: RepositoryReleaseDataUpdateCoordinator

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.name[:255]

    @property
    def extra_state_attributes(self) -> Mapping[str, str | None]:
        """Return the extra state attributes."""
        release = self.coordinator.data
        return {
            "url": release.html_url,
            "tag": release.tag_name,
        }


class GitHubSensorLatestIssueEntity(GitHubSensorLatestBaseEntity):
    """Defines a GitHub latest issue sensor entity."""

    _name: str = "Latest Issue"
    _coordinator_key: CoordinatorKeyType = "issue"

    coordinator: RepositoryIssueDataUpdateCoordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.issues_count != 0

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (issue := self.coordinator.data.issue_last) is None:
            return None
        return issue.title[:255]

    @property
    def extra_state_attributes(self) -> Mapping[str, str | int | None] | None:
        """Return the extra state attributes."""
        if (issue := self.coordinator.data.issue_last) is None:
            return None
        return {
            "url": issue.html_url,
            "number": issue.number,
        }


class GitHubSensorLatestPullEntity(GitHubSensorLatestBaseEntity):
    """Defines a GitHub latest pull sensor entity."""

    _coordinator_key: CoordinatorKeyType = "issue"
    _name: str = "Latest Pull Request"

    coordinator: RepositoryIssueDataUpdateCoordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.pulls_count != 0

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (pull := self.coordinator.data.pull_last) is None:
            return None
        return pull.title[:255]

    @property
    def extra_state_attributes(self) -> Mapping[str, str | int | None] | None:
        """Return the extra state attributes."""
        if (pull := self.coordinator.data.pull_last) is None:
            return None
        return {
            "url": pull.html_url,
            "number": pull.number,
        }


class GitHubSensorLatestCommitEntity(GitHubSensorLatestBaseEntity):
    """Defines a GitHub latest commit sensor entity."""

    _coordinator_key: CoordinatorKeyType = "commit"
    _name: str = "Latest Commit"

    coordinator: RepositoryCommitDataUpdateCoordinator

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.commit.message.splitlines()[0][:255]

    @property
    def extra_state_attributes(self) -> Mapping[str, str | int | None]:
        """Return the extra state attributes."""
        return {
            "sha": self.coordinator.data.sha,
            "url": self.coordinator.data.html_url,
        }
