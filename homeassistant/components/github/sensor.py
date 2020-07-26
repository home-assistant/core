"""Sensor platform for GitHub integration."""
from datetime import timedelta
import logging

from aiogithubapi.objects.repository import AIOGitHubAPIRepository

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import GitHubData, GitHubDeviceEntity
from .const import DATA_COORDINATOR, DATA_REPOSITORY, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLONES = "clones"
ATTR_CLONES_UNIQUE = "clones_unique"
ATTR_DESCRIPTION = "description"
ATTR_FORKS = "forks"
ATTR_HOMEPAGE = "homepage"
ATTR_LATEST_COMMIT_MESSAGE = "latest_commit_message"
ATTR_LATEST_COMMIT_SHA = "latest_commit_sha"
ATTR_LATEST_OPEN_ISSUE_URL = "latest_open_issue_url"
ATTR_LATEST_OPEN_PULL_REQUEST_URL = "latest_open_pull_request_url"
ATTR_LATEST_RELEASE_TAG = "latest_release_tag"
ATTR_LATEST_RELEASE_URL = "latest_release_url"
ATTR_OPEN_ISSUES = "open_issues"
ATTR_OPEN_PULL_REQUESTS = "open_pull_requests"
ATTR_PATH = "path"
ATTR_STARGAZERS = "stargazers"
ATTR_TOPICS = "topics"
ATTR_VIEWS = "views"
ATTR_VIEWS_UNIQUE = "views_unique"
ATTR_WATCHERS = "watchers"

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

    async_add_entities([RepositorySensor(coordinator, repository)], True)


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
        super().__init__(coordinator, f"{repository.full_name}_{unique_id}", name, icon)


class RepositorySensor(GitHubSensor):
    """Representation of a Repository Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, repository: AIOGitHubAPIRepository
    ) -> None:
        """Initialize the sensor."""
        self._clones = None
        self._clones_unique = None
        self._description = None
        self._forks = None
        self._homepage = None
        self._latest_commit_message = None
        self._latest_commit_sha = None
        self._latest_open_issue_url = None
        self._latest_open_pr_url = None
        self._latest_release_tag = None
        self._latest_release_url = None
        self._open_issues = None
        self._pull_requests = None
        self._repo_name = None
        self._stargazers = None
        self._state = None
        self._topics = None
        self._views = None
        self._views_unique = None
        self._watchers = None

        name = repository.attributes.get("name")

        super().__init__(
            coordinator, repository, "repository", f"{name} Repository", "mdi:github"
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_CLONES: self._clones,
            ATTR_CLONES_UNIQUE: self._clones_unique,
            ATTR_DESCRIPTION: self._description,
            ATTR_FORKS: self._forks,
            ATTR_HOMEPAGE: self._homepage,
            ATTR_LATEST_COMMIT_MESSAGE: self._latest_commit_message,
            ATTR_LATEST_COMMIT_SHA: self._latest_commit_sha,
            ATTR_LATEST_OPEN_ISSUE_URL: self._latest_open_issue_url,
            ATTR_LATEST_OPEN_PULL_REQUEST_URL: self._latest_open_pr_url,
            ATTR_LATEST_RELEASE_TAG: self._latest_release_tag,
            ATTR_LATEST_RELEASE_URL: self._latest_release_url,
            ATTR_NAME: self._repo_name,
            ATTR_OPEN_ISSUES: self._open_issues,
            ATTR_OPEN_PULL_REQUESTS: self._pull_requests,
            ATTR_STARGAZERS: self._stargazers,
            ATTR_TOPICS: self._topics,
            ATTR_VIEWS: self._views,
            ATTR_VIEWS_UNIQUE: self._views_unique,
            ATTR_WATCHERS: self._watchers,
        }

    async def _github_update(self) -> bool:
        """Fetch new state data for the sensor."""
        data: GitHubData = self._coordinator.data

        self._state = data.last_commit.sha_short

        self._clones = data.clones.count
        self._clones_unique = data.clones.count_uniques
        self._description = data.repository.description
        self._forks = data.repository.attributes.get("forks")
        self._homepage = data.repository.attributes.get("homepage")
        self._latest_commit_message = data.last_commit.message
        self._latest_commit_sha = data.last_commit.sha
        self._latest_open_issue_url = (
            data.open_issues[0].html_url if len(data.open_issues) > 1 else ""
        )
        self._latest_open_pr_url = (
            data.open_pull_requests[0].html_url
            if len(data.open_pull_requests) > 1
            else ""
        )
        self._latest_release_tag = (
            data.releases[0].tag_name if len(data.releases) > 1 else ""
        )
        self._latest_release_url = (
            f"https://github.com/{data.repository.full_name}/releases/{data.releases[0].tag_name}"
            if len(data.releases) > 1
            else ""
        )
        self._open_issues = len(data.open_issues)
        self._pull_requests = len(data.open_pull_requests)
        self._repo_name = data.repository.attributes.get("name")
        self._stargazers = data.repository.attributes.get("stargazers_count")
        self._topics = data.repository.topics
        self._views = data.views.count
        self._views_unique = data.views.count_uniques
        self._watchers = data.repository.attributes.get("watchers_count")

        return True
