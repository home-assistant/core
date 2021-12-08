"""Sensor platform for the GitHub integratiom."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiogithubapi import GitHubAPI, GitHubException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_NAME,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_PATH,
    CONF_URL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_REPOS = "repositories"

ATTR_LATEST_COMMIT_MESSAGE = "latest_commit_message"
ATTR_LATEST_COMMIT_SHA = "latest_commit_sha"
ATTR_LATEST_RELEASE_TAG = "latest_release_tag"
ATTR_LATEST_RELEASE_URL = "latest_release_url"
ATTR_LATEST_OPEN_ISSUE_URL = "latest_open_issue_url"
ATTR_OPEN_ISSUES = "open_issues"
ATTR_LATEST_OPEN_PULL_REQUEST_URL = "latest_open_pull_request_url"
ATTR_OPEN_PULL_REQUESTS = "open_pull_requests"
ATTR_PATH = "path"
ATTR_STARGAZERS = "stargazers"
ATTR_FORKS = "forks"
ATTR_CLONES = "clones"
ATTR_CLONES_UNIQUE = "clones_unique"
ATTR_VIEWS = "views"
ATTR_VIEWS_UNIQUE = "views_unique"

DEFAULT_NAME = "GitHub"

SCAN_INTERVAL = timedelta(seconds=300)

REPO_SCHEMA = vol.Schema(
    {vol.Required(CONF_PATH): cv.string, vol.Optional(CONF_NAME): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_URL): cv.url,
        vol.Required(CONF_REPOS): vol.All(cv.ensure_list, [REPO_SCHEMA]),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the GitHub sensor platform."""
    sensors = []
    session = async_get_clientsession(hass)
    for repository in config[CONF_REPOS]:
        data = GitHubData(
            repository=repository,
            access_token=config[CONF_ACCESS_TOKEN],
            session=session,
            server_url=config.get(CONF_URL),
        )
        sensors.append(GitHubSensor(data))
    async_add_entities(sensors, True)


class GitHubSensor(SensorEntity):
    """Representation of a GitHub sensor."""

    _attr_icon = "mdi:github"

    def __init__(self, github_data):
        """Initialize the GitHub sensor."""
        self._attr_unique_id = github_data.repository_path
        self._repository_path = None
        self._latest_commit_message = None
        self._latest_commit_sha = None
        self._latest_release_tag = None
        self._latest_release_url = None
        self._open_issue_count = None
        self._latest_open_issue_url = None
        self._pull_request_count = None
        self._latest_open_pr_url = None
        self._stargazers = None
        self._forks = None
        self._clones = None
        self._clones_unique = None
        self._views = None
        self._views_unique = None
        self._github_data = github_data

    async def async_update(self):
        """Collect updated data from GitHub API."""
        await self._github_data.async_update()
        self._attr_available = self._github_data.available
        if not self.available:
            return

        self._attr_name = self._github_data.name
        self._attr_native_value = self._github_data.last_commit.sha[0:7]

        self._latest_commit_message = self._github_data.last_commit.commit.message
        self._latest_commit_sha = self._github_data.last_commit.sha
        self._stargazers = self._github_data.repository_response.data.stargazers_count
        self._forks = self._github_data.repository_response.data.forks_count

        self._pull_request_count = len(self._github_data.pulls_response.data)
        self._open_issue_count = (
            self._github_data.repository_response.data.open_issues_count or 0
        ) - self._pull_request_count

        if self._github_data.last_release:
            self._latest_release_tag = self._github_data.last_release.tag_name
            self._latest_release_url = self._github_data.last_release.html_url

        if self._github_data.last_issue:
            self._latest_open_issue_url = self._github_data.last_issue.html_url

        if self._github_data.last_pull_request:
            self._latest_open_pr_url = self._github_data.last_pull_request.html_url

        if self._github_data.clones_response:
            self._clones = self._github_data.clones_response.data.count
            self._clones_unique = self._github_data.clones_response.data.uniques

        if self._github_data.views_response:
            self._views = self._github_data.views_response.data.count
            self._views_unique = self._github_data.views_response.data.uniques

        self._attr_extra_state_attributes = {
            ATTR_PATH: self._github_data.repository_path,
            ATTR_NAME: self.name,
            ATTR_LATEST_COMMIT_MESSAGE: self._latest_commit_message,
            ATTR_LATEST_COMMIT_SHA: self._latest_commit_sha,
            ATTR_LATEST_RELEASE_URL: self._latest_release_url,
            ATTR_LATEST_OPEN_ISSUE_URL: self._latest_open_issue_url,
            ATTR_OPEN_ISSUES: self._open_issue_count,
            ATTR_LATEST_OPEN_PULL_REQUEST_URL: self._latest_open_pr_url,
            ATTR_OPEN_PULL_REQUESTS: self._pull_request_count,
            ATTR_STARGAZERS: self._stargazers,
            ATTR_FORKS: self._forks,
        }
        if self._latest_release_tag is not None:
            self._attr_extra_state_attributes[
                ATTR_LATEST_RELEASE_TAG
            ] = self._latest_release_tag
        if self._clones is not None:
            self._attr_extra_state_attributes[ATTR_CLONES] = self._clones
        if self._clones_unique is not None:
            self._attr_extra_state_attributes[ATTR_CLONES_UNIQUE] = self._clones_unique
        if self._views is not None:
            self._attr_extra_state_attributes[ATTR_VIEWS] = self._views
        if self._views_unique is not None:
            self._attr_extra_state_attributes[ATTR_VIEWS_UNIQUE] = self._views_unique


class GitHubData:
    """GitHub Data object."""

    def __init__(self, repository, access_token, session, server_url=None):
        """Set up GitHub."""
        self._repository = repository
        self.repository_path = repository[CONF_PATH]
        self._github = GitHubAPI(
            token=access_token, session=session, **{"base_url": server_url}
        )

        self.available = False
        self.repository_response = None
        self.commit_response = None
        self.issues_response = None
        self.pulls_response = None
        self.releases_response = None
        self.views_response = None
        self.clones_response = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._repository.get(CONF_NAME, self.repository_response.data.name)

    @property
    def last_commit(self):
        """Return the last issue."""
        return self.commit_response.data[0] if self.commit_response.data else None

    @property
    def last_issue(self):
        """Return the last issue."""
        return self.issues_response.data[0] if self.issues_response.data else None

    @property
    def last_pull_request(self):
        """Return the last pull request."""
        return self.pulls_response.data[0] if self.pulls_response.data else None

    @property
    def last_release(self):
        """Return the last release."""
        return self.releases_response.data[0] if self.releases_response.data else None

    async def async_update(self):
        """Update GitHub data."""
        try:
            await asyncio.gather(
                self._update_repository(),
                self._update_commit(),
                self._update_issues(),
                self._update_pulls(),
                self._update_releases(),
            )

            if self.repository_response.data.permissions.push:
                await asyncio.gather(
                    self._update_clones(),
                    self._update_views(),
                )

            self.available = True
        except GitHubException as err:
            _LOGGER.error("GitHub error for %s: %s", self.repository_path, err)
            self.available = False

    async def _update_repository(self):
        """Update repository data."""
        self.repository_response = await self._github.repos.get(self.repository_path)

    async def _update_commit(self):
        """Update commit data."""
        self.commit_response = await self._github.repos.list_commits(
            self.repository_path, **{"params": {"per_page": 1}}
        )

    async def _update_issues(self):
        """Update issues data."""
        self.issues_response = await self._github.repos.issues.list(
            self.repository_path
        )

    async def _update_releases(self):
        """Update releases data."""
        self.releases_response = await self._github.repos.releases.list(
            self.repository_path
        )

    async def _update_clones(self):
        """Update clones data."""
        self.clones_response = await self._github.repos.traffic.clones(
            self.repository_path
        )

    async def _update_views(self):
        """Update views data."""
        self.views_response = await self._github.repos.traffic.views(
            self.repository_path
        )

    async def _update_pulls(self):
        """Update pulls data."""
        response = await self._github.repos.pulls.list(
            self.repository_path, **{"params": {"per_page": 100}}
        )
        if not response.is_last_page:
            results = await asyncio.gather(
                *(
                    self._github.repos.pulls.list(
                        self.repository_path,
                        **{"params": {"per_page": 100, "page": page_number}},
                    )
                    for page_number in range(
                        response.next_page_number, response.last_page_number + 1
                    )
                )
            )
            for result in results:
                response.data.extend(result.data)

        self.pulls_response = response
