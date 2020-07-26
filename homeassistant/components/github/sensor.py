"""Sensor platform for GitHub integration."""
from datetime import timedelta
import logging

from aiogithubapi.objects.repository import AIOGitHubAPIRepository

from homeassistant.const import ATTR_DATE, ATTR_ID, ATTR_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import GitHubData, GitHubDeviceEntity
from .const import DATA_COORDINATOR, DATA_REPOSITORY, DOMAIN

_LOGGER = logging.getLogger(__name__)


ATTR_ASSIGNEES = "assignees"
ATTR_CLONES = "clones"
ATTR_DRAFT = "draft"
ATTR_LABELS = "labels"
ATTR_MESSAGE = "message"
ATTR_NUMBER = "number"
ATTR_OPEN = "open"
ATTR_PRERELEASE = "prerelease"
ATTR_RELEASES = "releases"
ATTR_REPO_DESCRIPTION = "repository_description"
ATTR_REPO_HOMEPAGE = "repository_homepage"
ATTR_REPO_NAME = "repository_name"
ATTR_REPO_PATH = "repository_path"
ATTR_REPO_TOPICS = "repository_topics"
ATTR_SHA = "sha"
ATTR_UNIQUE = "unique"
ATTR_URL = "url"
ATTR_USER = "user"

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    repository: AIOGitHubAPIRepository = hass.data[DOMAIN][entry.entry_id][
        DATA_REPOSITORY
    ]

    async_add_entities(
        [
            ClonesSensor(coordinator, repository),
            ForksSensor(coordinator, repository),
            LatestCommitSensor(coordinator, repository),
            LatestOpenIssueSensor(coordinator, repository),
            LatestPullRequestSensor(coordinator, repository),
            LatestReleaseSensor(coordinator, repository),
            StargazersSensor(coordinator, repository),
            ViewsSensor(coordinator, repository),
            WatchersSensor(coordinator, repository),
        ],
        True,
    )


class GitHubSensor(GitHubDeviceEntity):
    """Representation of a GitHub sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        repository: AIOGitHubAPIRepository,
        unique_id: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        self._state = None
        self._attributes = None

        super().__init__(coordinator, f"{repository.full_name}_{unique_id}", name, icon)

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        return self._attributes


class ClonesSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "clones", f"{name} Clones", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.clones.count

        self._attributes = {
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
            ATTR_UNIQUE: data.clones.count_uniques,
        }

        return True


class ForksSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "forks", f"{name} Forks", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.repository.attributes.get("forks")

        self._attributes = {
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
        }

        return True


class LatestCommitSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "last_commit", f"{name} Last Commit", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.last_commit.sha_short

        self._attributes = {
            ATTR_MESSAGE: data.last_commit.message,
            ATTR_SHA: data.last_commit.sha,
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
        }

        return True


class LatestOpenIssueSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator,
            repository,
            "latest_open_issue",
            f"{name} Latest Open Issue",
            "mdi:github",
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        if data.open_issues is None or len(data.open_issues) < 1:
            return False

        self._state = data.open_issues[0].title

        labels = []
        for label in data.open_issues[0].labels:
            labels.append(label.get("name"))

        self._attributes = {
            ATTR_ASSIGNEES: data.open_issues[0].assignees,
            ATTR_ID: data.open_issues[0].id,
            ATTR_LABELS: labels,
            ATTR_NUMBER: data.open_issues[0].number,
            ATTR_OPEN: len(data.open_issues),
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
            ATTR_URL: data.open_issues[0].html_url,
            ATTR_USER: data.open_issues[0].user.login,
        }

        return True


class LatestPullRequestSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator,
            repository,
            "latest_pull_request",
            f"{name} Latest Pull Request",
            "mdi:github",
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        if data.open_pull_requests is None or len(data.open_pull_requests) < 1:
            return False

        self._state = data.open_pull_requests[0].title

        labels = []
        for label in data.open_pull_requests[0].labels:
            labels.append(label.get("name"))

        self._attributes = {
            ATTR_ASSIGNEES: data.open_pull_requests[0].assignees,
            ATTR_ID: data.open_pull_requests[0].id,
            ATTR_LABELS: labels,
            ATTR_NUMBER: data.open_pull_requests[0].number,
            ATTR_OPEN: len(data.open_pull_requests),
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
            ATTR_USER: data.open_pull_requests[0].user.login,
        }

        return True


class LatestReleaseSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator,
            repository,
            "latest_release",
            f"{name} Latest Release",
            "mdi:github",
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        if data.releases is None or len(data.releases) < 1:
            return False

        self._state = data.releases[0].tag_name

        self._attributes = {
            ATTR_DATE: data.releases[0].published_at,
            ATTR_DRAFT: data.releases[0].draft,
            ATTR_NAME: data.releases[0].name,
            ATTR_PRERELEASE: data.releases[0].prerelease,
            ATTR_RELEASES: len(data.releases),
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
            ATTR_URL: f"https://github.com/{data.repository.full_name}/releases/{data.releases[0].tag_name}",
        }

        return True


class StargazersSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "stargazers", f"{name} Stargazers", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.repository.attributes.get("stargazers_count")

        self._attributes = {
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
        }

        return True


class ViewsSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "views", f"{name} Views", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.views.count

        self._attributes = {
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
            ATTR_UNIQUE: data.views.count_uniques,
        }

        return True


class WatchersSensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        name = repository.attributes.get("name")
        super().__init__(
            coordinator, repository, "watchers", f"{name} Watchers", "mdi:github"
        )

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.repository.attributes.get("watchers_count")

        self._attributes = {
            ATTR_REPO_DESCRIPTION: data.repository.description,
            ATTR_REPO_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_REPO_NAME: data.repository.attributes.get("name"),
            ATTR_REPO_PATH: data.repository.full_name,
            ATTR_REPO_TOPICS: data.repository.topics,
        }

        return True
