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

    async_add_entities([LastCommitSensor(coordinator, repository)], True)


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


class LastCommitSensor(GitHubSensor):
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
            ATTR_CLONES: data.clones.count,
            ATTR_CLONES_UNIQUE: data.clones.count_uniques,
            ATTR_DESCRIPTION: data.repository.description,
            ATTR_FORKS: data.repository.attributes.get("forks"),
            ATTR_HOMEPAGE: data.repository.attributes.get("homepage"),
            ATTR_LATEST_COMMIT_MESSAGE: data.last_commit.message,
            ATTR_LATEST_COMMIT_SHA: data.last_commit.sha,
            ATTR_LATEST_OPEN_ISSUE_URL: (
                data.open_issues[0].html_url if len(data.open_issues) > 1 else ""
            ),
            ATTR_LATEST_OPEN_PULL_REQUEST_URL: (
                data.open_pull_requests[0].html_url
                if len(data.open_pull_requests) > 1
                else None
            ),
            ATTR_LATEST_RELEASE_TAG: (
                data.releases[0].tag_name if len(data.releases) > 1 else ""
            ),
            ATTR_LATEST_RELEASE_URL: (
                f"https://github.com/{data.repository.full_name}/releases/{data.releases[0].tag_name}"
                if len(data.releases) > 1
                else None
            ),
            ATTR_OPEN_ISSUES: len(data.open_issues),
            ATTR_OPEN_PULL_REQUESTS: len(data.open_pull_requests),
            ATTR_NAME: data.repository.attributes.get("name"),
            ATTR_PATH: data.repository.full_name,
            ATTR_STARGAZERS: data.repository.attributes.get("stargazers_count"),
            ATTR_TOPICS: data.repository.topics,
            ATTR_VIEWS: data.views.count,
            ATTR_VIEWS_UNIQUE: data.views.count_uniques,
            ATTR_WATCHERS: data.repository.attributes.get("watchers_count"),
        }

        return True
