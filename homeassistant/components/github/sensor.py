"""Sensor platform for the GitHub integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aiogithubapi import GitHubAuthenticatedUserModel

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    GithubConfigEntry,
    GitHubDataUpdateCoordinator,
    GitHubUserDataUpdateCoordinator,
)


@dataclass(frozen=True, kw_only=True)
class GitHubSensorEntityDescription(SensorEntityDescription):
    """Describes GitHub issue sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]

    attr_fn: Callable[[dict[str, Any]], Mapping[str, Any] | None] = lambda data: None
    avabl_fn: Callable[[dict[str, Any]], bool] = lambda data: True


SENSOR_DESCRIPTIONS: tuple[GitHubSensorEntityDescription, ...] = (
    GitHubSensorEntityDescription(
        key="discussions_count",
        translation_key="discussions_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["discussion"]["total"],
    ),
    GitHubSensorEntityDescription(
        key="stargazers_count",
        translation_key="stargazers_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["stargazers_count"],
    ),
    GitHubSensorEntityDescription(
        key="subscribers_count",
        translation_key="subscribers_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["watchers"]["total"],
    ),
    GitHubSensorEntityDescription(
        key="forks_count",
        translation_key="forks_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["forks_count"],
    ),
    GitHubSensorEntityDescription(
        key="issues_count",
        translation_key="issues_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["issue"]["total"],
    ),
    GitHubSensorEntityDescription(
        key="pulls_count",
        translation_key="pulls_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["pull_request"]["total"],
    ),
    GitHubSensorEntityDescription(
        key="merged_pulls_count",
        translation_key="merged_pulls_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["merged_pull_request"]["total"],
    ),
    GitHubSensorEntityDescription(
        key="latest_commit",
        translation_key="latest_commit",
        value_fn=lambda data: data["default_branch_ref"]["commit"]["message"][:255],
        attr_fn=lambda data: {
            "sha": data["default_branch_ref"]["commit"]["sha"],
            "url": data["default_branch_ref"]["commit"]["url"],
        },
    ),
    GitHubSensorEntityDescription(
        key="latest_discussion",
        translation_key="latest_discussion",
        avabl_fn=lambda data: data["discussion"]["discussions"],
        value_fn=lambda data: data["discussion"]["discussions"][0]["title"][:255],
        attr_fn=lambda data: {
            "url": data["discussion"]["discussions"][0]["url"],
            "number": data["discussion"]["discussions"][0]["number"],
        },
    ),
    GitHubSensorEntityDescription(
        key="latest_release",
        translation_key="latest_release",
        avabl_fn=lambda data: data["release"] is not None,
        value_fn=lambda data: data["release"]["name"][:255],
        attr_fn=lambda data: {
            "url": data["release"]["url"],
            "tag": data["release"]["tag"],
        },
    ),
    GitHubSensorEntityDescription(
        key="latest_issue",
        translation_key="latest_issue",
        avabl_fn=lambda data: data["issue"]["issues"],
        value_fn=lambda data: data["issue"]["issues"][0]["title"][:255],
        attr_fn=lambda data: {
            "url": data["issue"]["issues"][0]["url"],
            "number": data["issue"]["issues"][0]["number"],
        },
    ),
    GitHubSensorEntityDescription(
        key="latest_pull_request",
        translation_key="latest_pull_request",
        avabl_fn=lambda data: data["pull_request"]["pull_requests"],
        value_fn=lambda data: data["pull_request"]["pull_requests"][0]["title"][:255],
        attr_fn=lambda data: {
            "url": data["pull_request"]["pull_requests"][0]["url"],
            "number": data["pull_request"]["pull_requests"][0]["number"],
        },
    ),
    GitHubSensorEntityDescription(
        key="latest_tag",
        translation_key="latest_tag",
        avabl_fn=lambda data: data["refs"]["tags"],
        value_fn=lambda data: data["refs"]["tags"][0]["name"][:255],
        attr_fn=lambda data: {
            "url": data["refs"]["tags"][0]["target"]["url"],
        },
    ),
)


@dataclass(frozen=True, kw_only=True)
class GitHubUserSensorEntityDescription(SensorEntityDescription):
    """Describes GitHub user sensor entity."""

    value_fn: Callable[[GitHubAuthenticatedUserModel], StateType]


USER_SENSOR_DESCRIPTIONS: tuple[GitHubUserSensorEntityDescription, ...] = (
    GitHubUserSensorEntityDescription(
        key="followers",
        translation_key="followers",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.followers,
    ),
    GitHubUserSensorEntityDescription(
        key="following",
        translation_key="following",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.following,
    ),
    GitHubUserSensorEntityDescription(
        key="public_gists",
        translation_key="public_gists",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.public_gists,
    ),
    GitHubUserSensorEntityDescription(
        key="public_repos",
        translation_key="public_repos",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.public_repos,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GithubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GitHub sensor based on a config entry."""
    user_coordinator = entry.runtime_data.user_coordinator
    async_add_entities(
        GitHubUserSensorEntity(user_coordinator, description)
        for description in USER_SENSOR_DESCRIPTIONS
    )

    for subentry_id, coordinator in entry.runtime_data.repositories.items():
        async_add_entities(
            (
                GitHubSensorEntity(coordinator, description)
                for description in SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry_id,
        )


class GitHubSensorEntity(CoordinatorEntity[GitHubDataUpdateCoordinator], SensorEntity):
    """Defines a GitHub sensor entity."""

    _attr_attribution = "Data provided by the GitHub API"
    _attr_has_entity_name = True

    entity_description: GitHubSensorEntityDescription

    def __init__(
        self,
        coordinator: GitHubDataUpdateCoordinator,
        entity_description: GitHubSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.get('id')}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.repository)},
            name=coordinator.data.get("full_name"),
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


class GitHubUserSensorEntity(
    CoordinatorEntity[GitHubUserDataUpdateCoordinator], SensorEntity
):
    """Defines a GitHub user sensor entity."""

    _attr_has_entity_name = True

    entity_description: GitHubUserSensorEntityDescription

    def __init__(
        self,
        coordinator: GitHubUserDataUpdateCoordinator,
        entity_description: GitHubUserSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.id}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.data.id))},
            name=coordinator.data.login,
            manufacturer="GitHub",
            configuration_url=f"https://github.com/{coordinator.data.login}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
