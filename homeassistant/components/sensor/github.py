"""
Support for GitHub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.github/
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME, CONF_ACCESS_TOKEN, CONF_NAME, CONF_PASSWORD, CONF_PATH,
    CONF_URL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['PyGithub==1.43.5']

_LOGGER = logging.getLogger(__name__)

CONF_GROUP_AUTH = 'authentication'
CONF_REPOS = 'repositories'

ATTR_BRANCHES = 'branches'
ATTR_LAST_COMMIT = 'last_commit'
ATTR_LATEST_RELEASE = 'latest_release'
ATTR_OPEN_ISSUES = 'open_issues'
ATTR_OPEN_PULL_REQUESTS = 'open_pull_requests'
ATTR_PATH = 'path'
ATTR_STARGAZERS = 'stargazers'
ATTR_TOPICS = 'topics'

DEFAULT_NAME = 'GitHub'

SCAN_INTERVAL = timedelta(seconds=300)

REPO_SCHEMA = vol.Schema({
    vol.Required(CONF_PATH): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Exclusive(CONF_ACCESS_TOKEN, CONF_GROUP_AUTH): cv.string,
    vol.Exclusive(CONF_USERNAME, CONF_GROUP_AUTH): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_URL): cv.url,
    vol.Required(CONF_REPOS):
        vol.All(cv.ensure_list, [REPO_SCHEMA])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GitHub sensor platform."""
    if config.get(CONF_ACCESS_TOKEN) is None \
            and config.get(CONF_USERNAME) is None:
        # Error if there is no authentication set
        _LOGGER.error("You have not set an access_token or a username")
        return

    sensors = []
    for repository in config[CONF_REPOS]:
        data = GitHubData(
            repository=repository,
            access_token=config.get(CONF_ACCESS_TOKEN),
            username=config.get(CONF_USERNAME),
            password=config.get(CONF_PASSWORD),
            server_url=config.get(CONF_URL)
        )
        if data.setup_error is True:
            _LOGGER.error("Error setting up GitHub platform. %s",
                          "Check previous errors for details")
            return
        sensors.append(GitHubSensor(data))
    add_entities(sensors, True)


class GitHubSensor(Entity):
    """Representation of a GitHub sensor."""

    def __init__(self, github_data):
        """Initialize the GitHub sensor."""
        self._available = False
        self._state = None
        self._repository_path = None
        self._name = None
        self._stargazers = None
        self._topics = None
        self._branches = None
        self._open_issues = None
        self._open_pull_requests = None
        self._last_commit = None
        self._latest_release = None
        self._github_data = github_data

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
            ATTR_PATH: self._repository_path,
            ATTR_NAME: self._name,
            ATTR_STARGAZERS: self._stargazers,
            ATTR_TOPICS: self._topics,
            ATTR_BRANCHES: self._branches,
            ATTR_OPEN_ISSUES: self._open_issues,
            ATTR_OPEN_PULL_REQUESTS: self._open_pull_requests,
            ATTR_LAST_COMMIT: self._last_commit,
            ATTR_LATEST_RELEASE: self._latest_release
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:github-circle'

    def update(self):
        """Collect updated data from GitHub API."""
        self._github_data.update()

        self._state = self._github_data.last_commit_sha
        self._repository_path = self._github_data.repository_path
        self._name = self._github_data.name
        self._stargazers = self._github_data.stargazers
        self._topics = self._github_data.topics
        self._branches = self._github_data.branches
        self._open_issues = self._github_data.open_issues
        self._open_pull_requests = self._github_data.open_pull_requests
        self._last_commit = self._github_data.last_commit
        self._latest_release = self._github_data.latest_release
        self._available = self._github_data.available


class GitHubData():
    """GitHub Data object."""

    def __init__(self, repository, access_token=None, username=None,
                 password=None, server_url=None):
        """Set up GitHub."""
        import github

        self._github = github

        self.setup_error = False

        try:
            if server_url is not None:
                server_url += "/api/v3"
                if access_token is not None:
                    self._github_obj = github.Github(
                        access_token, base_url=server_url)
                elif username is not None and password is not None:
                    self._github_obj = github.Github(
                        username, password, base_url=server_url)
            else:
                if access_token is not None:
                    self._github_obj = github.Github(access_token)
                elif username is not None and password is not None:
                    self._github_obj = github.Github(username, password)

            self.repository_path = repository[CONF_PATH]

            repo = self._github_obj.get_repo(self.repository_path)
        except self._github.GithubException as err:
            _LOGGER.error("GitHub error for %s: %s",
                          self.repository_path, err)
            self.setup_error = True
            return

        if CONF_NAME in repository:
            self.name = repository[CONF_NAME]
        else:
            self.name = repo.name

        self.update = self._update

        self.stargazers = None
        self.topics = None
        self.branches = None
        self.open_issues = None
        self.open_pull_requests = None
        self.last_commit = None
        self.latest_release = None
        self.available = False

    def _update(self):
        """Update GitHub Sensor."""
        try:
            repo = self._github_obj.get_repo(self.repository_path)

            self.stargazers = repo.stargazers_count

            open_issues = repo.get_issues(state='open', sort='created')
            if open_issues is not None and len(open_issues) > 0:
                self.open_issue_count = len(open_issues)
                self.open_issue_latest = open_issues[0].html_url

            open_pull_requests = repo.get_pulls(state='open', sort='created')
            if open_pull_requests is not None and len(open_pull_requests) > 0:
                self.pull_request_count = len(open_pull_requests)
                self.pull_request_latest = open_pull_requests[0].html_url

            last_commit = repo.get_commits()[0]
            self.last_commit_sha = last_commit.sha
            self.last_commit_message: last_commit.commit.message

            releases = repo.get_releases()
            if releases and releases.totalCount > 0:
                self.latest_release_url = releases[0].html_url

            self.available = True
        except self._github.GithubException as err:
            _LOGGER.error("GitHub error for %s: %s",
                          self.repository_path, err)
            self.available = False
