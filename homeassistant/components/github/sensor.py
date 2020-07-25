"""Sensor platform for GitHub integration."""
from datetime import timedelta
import logging

from aiogithubapi import GitHub
from aiogithubapi.objects.repository import (
    AIOGitHubAPIRepository,
    AIOGitHubAPIRepositoryIssue,
    AIOGitHubAPIRepositoryRelease,
)

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import Entity

from .const import CONF_REPOSITORY, DOMAIN

_LOGGER = logging.getLogger(__name__)

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
ATTR_WATCHERS = "watchers"

SCAN_INTERVAL = timedelta(seconds=300)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    github = hass.data[DOMAIN][entry.entry_id]
    repository = entry.data[CONF_REPOSITORY]

    async_add_entities([RepositorySensor(github, repository)], True)


class RepositorySensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, github: GitHub, repository: str):
        """Initialize the sensor."""
        self._github = github
        self._repository = repository
        self._unique_id = f"{repository}_sensor"
        self._available = False
        self._description = None
        self._forks = None
        self._homepage = None
        self._latest_commit_message = None
        self._latest_commit_sha = None
        self._latest_open_issue_url = None
        self._latest_open_pr_url = None
        self._latest_release_tag = None
        self._latest_release_url = None
        self._name = None
        self._open_issues = None
        self._pull_requests = None
        self._stargazers = None
        self._state = None
        self._topics = None
        self._views = None
        self._views_unique = None
        self._watchers = None

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DESCRIPTION: self._description,
            ATTR_FORKS: self._forks,
            ATTR_LATEST_COMMIT_MESSAGE: self._latest_commit_message,
            ATTR_LATEST_COMMIT_SHA: self._latest_commit_sha,
            ATTR_LATEST_OPEN_ISSUE_URL: self._latest_open_issue_url,
            ATTR_LATEST_OPEN_PULL_REQUEST_URL: self._latest_open_pr_url,
            ATTR_LATEST_RELEASE_TAG: self._latest_release_tag,
            ATTR_LATEST_RELEASE_URL: self._latest_release_url,
            ATTR_NAME: self._name,
            ATTR_OPEN_ISSUES: self._open_issues,
            ATTR_OPEN_PULL_REQUESTS: self._pull_requests,
            ATTR_PATH: self._repository,
            ATTR_STARGAZERS: self._stargazers,
            ATTR_TOPICS: self._topics,
            ATTR_WATCHERS: self._watchers,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:github"

    async def async_update(self):
        """Fetch new state data for the sensor."""
        repository: AIOGitHubAPIRepository = await self._github.get_repo(
            self._repository
        )
        if repository is None:
            _LOGGER.error("Cannot find repository")
            self._available = False
            return

        last_commit = await repository.client.get(
            endpoint=f"/repos/{repository.full_name}/branches/{repository.default_branch}"
        )

        releases: AIOGitHubAPIRepositoryRelease = await repository.get_releases()

        all_issues: [AIOGitHubAPIRepositoryIssue] = await repository.get_issues()
        issues: [AIOGitHubAPIRepositoryIssue] = []
        pull_requests: [AIOGitHubAPIRepositoryIssue] = []
        for issue in all_issues:
            if issue.state == "open":
                if "pull" in issue.html_url:
                    pull_requests.append(issue)
                else:
                    issues.append(issue)

        self._state = last_commit["commit"]["sha"][0:7]

        self._name = repository.attributes.get("name")
        self._description = repository.description
        self._topics = repository.topics
        self._homepage = repository.attributes.get("homepage")
        self._latest_commit_sha = last_commit["commit"]["sha"]
        self._latest_release_tag = releases[0].tag_name if len(releases) > 1 else ""
        self._latest_release_url = (
            f"https://github.com/{repository.full_name}/releases/{releases[0].tag_name}"
            if len(releases) > 1
            else ""
        )
        self._stargazers = repository.attributes.get("stargazers_count")
        self._watchers = repository.attributes.get("watchers_count")
        self._forks = repository.attributes.get("forks")
        self._latest_commit_message = last_commit["commit"]["commit"][
            "message"
        ].splitlines()[0]
        self._open_issues = len(issues)
        self._pull_requests = len(pull_requests)
        self._latest_open_issue_url = issues[0].html_url if len(issues) > 1 else ""
        self._latest_open_pr_url = (
            pull_requests[0].html_url if len(pull_requests) > 1 else ""
        )

        self._available = True
