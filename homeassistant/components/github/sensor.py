"""Support for GitHub."""
from datetime import timedelta
import logging

import github
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_PATH,
    CONF_URL,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GitHub sensor platform."""
    sensors = []
    for repository in config[CONF_REPOS]:
        data = GitHubData(
            repository=repository,
            access_token=config.get(CONF_ACCESS_TOKEN),
            server_url=config.get(CONF_URL),
        )
        if data.setup_error is True:
            _LOGGER.error(
                "Error setting up GitHub platform. %s",
                "Check previous errors for details",
            )
        else:
            sensors.append(GitHubSensor(data))
    add_entities(sensors, True)


class GitHubSensor(Entity):
    """Representation of a GitHub sensor."""

    def __init__(self, github_data):
        """Initialize the GitHub sensor."""
        self._unique_id = github_data.repository_path
        self._name = None
        self._state = None
        self._available = False
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

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        return self._unique_id

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
        attrs = {
            ATTR_PATH: self._repository_path,
            ATTR_NAME: self._name,
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
            attrs[ATTR_LATEST_RELEASE_TAG] = self._latest_release_tag
        if self._clones is not None:
            attrs[ATTR_CLONES] = self._clones
        if self._clones_unique is not None:
            attrs[ATTR_CLONES_UNIQUE] = self._clones_unique
        if self._views is not None:
            attrs[ATTR_VIEWS] = self._views
        if self._views_unique is not None:
            attrs[ATTR_VIEWS_UNIQUE] = self._views_unique
        return attrs

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:github-circle"

    def update(self):
        """Collect updated data from GitHub API."""
        self._github_data.update()

        self._name = self._github_data.name
        self._repository_path = self._github_data.repository_path
        self._available = self._github_data.available
        self._latest_commit_message = self._github_data.latest_commit_message
        self._latest_commit_sha = self._github_data.latest_commit_sha
        if self._github_data.latest_release_url is not None:
            self._latest_release_tag = self._github_data.latest_release_url.split(
                "tag/"
            )[1]
        else:
            self._latest_release_tag = None
        self._latest_release_url = self._github_data.latest_release_url
        self._state = self._github_data.latest_commit_sha[0:7]
        self._open_issue_count = self._github_data.open_issue_count
        self._latest_open_issue_url = self._github_data.latest_open_issue_url
        self._pull_request_count = self._github_data.pull_request_count
        self._latest_open_pr_url = self._github_data.latest_open_pr_url
        self._stargazers = self._github_data.stargazers
        self._forks = self._github_data.forks
        self._clones = self._github_data.clones
        self._clones_unique = self._github_data.clones_unique
        self._views = self._github_data.views
        self._views_unique = self._github_data.views_unique


class GitHubData:
    """GitHub Data object."""

    def __init__(self, repository, access_token=None, server_url=None):
        """Set up GitHub."""
        self._github = github

        self.setup_error = False

        try:
            if server_url is not None:
                server_url += "/api/v3"
                self._github_obj = github.Github(access_token, base_url=server_url)
            else:
                self._github_obj = github.Github(access_token)

            self.repository_path = repository[CONF_PATH]

            repo = self._github_obj.get_repo(self.repository_path)
        except self._github.GithubException as err:
            _LOGGER.error("GitHub error for %s: %s", self.repository_path, err)
            self.setup_error = True
            return

        self.name = repository.get(CONF_NAME, repo.name)
        self.available = False
        self.latest_commit_message = None
        self.latest_commit_sha = None
        self.latest_release_url = None
        self.open_issue_count = None
        self.latest_open_issue_url = None
        self.pull_request_count = None
        self.latest_open_pr_url = None
        self.stargazers = None
        self.forks = None
        self.clones = None
        self.clones_unique = None
        self.views = None
        self.views_unique = None

    def update(self):
        """Update GitHub Sensor."""
        try:
            repo = self._github_obj.get_repo(self.repository_path)

            self.stargazers = repo.stargazers_count
            self.forks = repo.forks_count

            open_issues = repo.get_issues(state="open", sort="created")
            if open_issues is not None:
                self.open_issue_count = open_issues.totalCount
                if open_issues.totalCount > 0:
                    self.latest_open_issue_url = open_issues[0].html_url

            open_pull_requests = repo.get_pulls(state="open", sort="created")
            if open_pull_requests is not None:
                self.pull_request_count = open_pull_requests.totalCount
                if open_pull_requests.totalCount > 0:
                    self.latest_open_pr_url = open_pull_requests[0].html_url

            latest_commit = repo.get_commits()[0]
            self.latest_commit_sha = latest_commit.sha
            self.latest_commit_message = latest_commit.commit.message

            releases = repo.get_releases()
            if releases and releases.totalCount > 0:
                self.latest_release_url = releases[0].html_url

            if repo.permissions.push:
                clones = repo.get_clones_traffic()
                if clones is not None:
                    self.clones = clones.get("count")
                    self.clones_unique = clones.get("uniques")

                views = repo.get_views_traffic()
                if views is not None:
                    self.views = views.get("count")
                    self.views_unique = views.get("uniques")

            self.available = True
        except self._github.GithubException as err:
            _LOGGER.error("GitHub error for %s: %s", self.repository_path, err)
            self.available = False
