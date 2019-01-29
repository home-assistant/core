"""
Support for GitHub.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.github/
"""
from datetime import timedelta
import json
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME, CONF_ACCESS_TOKEN, CONF_NAME, CONF_PASSWORD, CONF_PATH,
    CONF_SCAN_INTERVAL, CONF_URL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

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
        vol.All(cv.ensure_list, [REPO_SCHEMA]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GitHub sensor platform."""
    if config.get(CONF_ACCESS_TOKEN) is None \
            and config.get(CONF_USERNAME) is None:
        # Error if there is no authentication set
        _LOGGER.error("You have not set an access_token or a username")
        return

    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    sensors = []
    for repository in config[CONF_REPOS]:
        sensors.append(GitHubSensor(GitHubData(
            interval=interval,
            repository=repository,
            access_token=config.get(CONF_ACCESS_TOKEN),
            username=config.get(CONF_USERNAME),
            password=config.get(CONF_PASSWORD),
            server_url=config.get(CONF_URL)
        )))
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

        self._state = self._github_data.stargazers
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

    def __init__(self, interval, repository, access_token=None, username=None,
                 password=None, server_url=None):
        """Set up GitHub."""
        import github

        self._github = github

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

        if CONF_NAME in repository:
            self.name = repository[CONF_NAME]
        else:
            self.name = repo.name

        self.update = Throttle(interval)(self._update)

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

            self.topics = json.dumps(repo.get_topics())

            branches = []
            for branch in repo.get_branches():
                branches.append(branch.name)
            self.branches = json.dumps(branches)

            open_issues = []
            for issue in repo.get_issues(state='open', sort='created'):
                if issue.pull_request is None:
                    labels = []
                    for label in issue.labels:
                        labels.append(label.name)
                    open_issues.append({
                        "number": issue.number,
                        "title": issue.title,
                        "url": issue.html_url,
                        "body": issue.body,
                        "labels": labels,
                        "assignee": issue.assignee,
                        "milestone": issue.milestone,
                        "comments": issue.comments,
                        "user": {
                            "login": issue.user.login,
                            "name": issue.user.name,
                            "avatar_url": issue.user.avatar_url,
                            "url": issue.user.html_url
                        }
                    })
            self.open_issues = json.dumps(open_issues)

            open_pull_requests = []
            for _pr in repo.get_pulls(state='open', sort='created'):
                labels = []
                for label in _pr.labels:
                    labels.append(label.name)
                open_pull_requests.append({
                    "number": _pr.number,
                    "title": _pr.title,
                    "url": _pr.html_url,
                    "body": _pr.body,
                    "labels": labels,
                    "assignee": _pr.assignee,
                    "milestone": _pr.milestone,
                    "comments": _pr.comments,
                    "user": {
                        "login": _pr.user.login,
                        "name": _pr.user.name,
                        "avatar_url": _pr.user.avatar_url,
                        "url": _pr.user.html_url
                    }
                })
            self.open_pull_requests = json.dumps(open_pull_requests)

            last_commit = repo.get_commits()[0]
            self.last_commit = json.dumps({
                "sha": last_commit.sha,
                "message": last_commit.commit.message,
                "url": last_commit.html_url,
                "author": {
                    "login": last_commit.author.login,
                    "name": last_commit.author.name,
                    "avatar_url": last_commit.author.avatar_url,
                    "url": last_commit.author.html_url
                }
            })

            releases = repo.get_releases()
            if releases and releases.totalCount > 0:
                self.latest_release = json.dumps({
                    "title": releases[0].title,
                    "tag": releases[0].tag_name,
                    "url": releases[0].html_url,
                    "created_at": str(releases[0].created_at),
                    "published_at": str(releases[0].published_at),
                    "body": releases[0].body
                })

            self.available = True
        except self._github.BadCredentialsException as err:
            _LOGGER.error("Bad Credentials for %s: %s",
                          self.repository_path, err)
            self.available = False
        except self._github.UnknownObjectException as err:
            _LOGGER.error("UnknownObjectException for %s: %s",
                          self.repository_path, err)
            self.available = False
        except self._github.RateLimitExceededException as err:
            _LOGGER.error("RateLimitExceededException for %s: %s",
                          self.repository_path, err)
            self.available = False
        except self._github.BadAttributeException as err:
            _LOGGER.error("BadAttributeException for %s: %s",
                          self.repository_path, err)
            self.available = False
        except self._github.TwoFactorException as err:
            _LOGGER.error("TwoFactorException for %s: %s",
                          self.repository_path, err)
            self.available = False
        except self._github.GithubException as err:
            _LOGGER.error("GithubException for %s: %s",
                          self.repository_path, err)
            self.available = False
