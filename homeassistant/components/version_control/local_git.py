"""
Support for monitoring a local git repository.

Creates entities that breakout information about
the specified local git repository.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/version_control.local_git/
"""
import logging

import voluptuous as vol
from homeassistant.components.version_control import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_NAME, CONF_PATH, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['gitpython==2.1.9']

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
ATTR_PATH = 'path'
ATTR_REMOTE = 'remote'
ATTR_RESET = 'reset'
ATTR_ACTIVE_COMMIT_SUMMARY = 'commit_summary'

SERVICE_LOCAL_GIT_PULL = 'local_git_pull'

DATA_LOCAL_GIT = 'local_git'

STATE_BARE = 'bare'
STATE_CLEAN = 'clean'
STATE_DIRTY = 'dirty'
STATE_INVALID = 'empty'

LOCAL_GIT_PULL_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_REMOTE, default='origin'): cv.string,
    vol.Optional(ATTR_RESET, default=False): cv.boolean
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PATH): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Git repository sensor."""
    from git import Repo

    if hass.data.get(DATA_LOCAL_GIT) is None:
        hass.data[DATA_LOCAL_GIT] = []

    entities = []

    repository = Repo(config.get(CONF_PATH))

    local_git_repo = GitRepo(name=config.get(CONF_NAME), repo=repository)
    local_git_repo_activebranch = GitRepoActiveBranch(
        name=config.get(CONF_NAME), repo=repository)
    local_git_repo_activecommit = GitRepoActiveCommit(
        name=config.get(CONF_NAME), repo=repository)

    entities.append(local_git_repo)
    entities.append(local_git_repo_activebranch)
    entities.append(local_git_repo_activecommit)

    hass.data[DATA_LOCAL_GIT].append(local_git_repo)
    add_entities(entities, update_before_add=True)

    def _local_git_pull_service(service):
        """Service to pull contents from remote repository."""
        target_repos = [repo for repo in hass.data[DATA_LOCAL_GIT]
                        if repo.entity_id in service.data.get(ATTR_ENTITY_ID)]

        for repo in target_repos:
            repo.git_pull(
                remote=service.data.get(ATTR_REMOTE),
                reset=service.data.get(ATTR_RESET)
            )
            repo.schedule_update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_LOCAL_GIT_PULL, _local_git_pull_service,
        schema=LOCAL_GIT_PULL_SERVICE_SCHEMA)


class GitRepoAttribute(Entity):
    """Representation of local Git repo attribute."""

    def __init__(self, name, repo):
        """Create a new local Git repo attribute."""
        self._repo = repo
        self._old_value = None
        self._name = name
        self._state = STATE_UNKNOWN

    @property
    def should_poll(self):
        """Polling is needed."""
        return True

    @property
    def name(self):
        """Return the name of the local Git repo attribute."""
        return self._name

    @property
    def state(self):
        """Return attribute state."""
        return self._state


class GitRepo(GitRepoAttribute):
    """Representation of local Git Repo."""

    def __init__(self, name, repo):
        """Create a new local Git repo entity."""
        GitRepoAttribute.__init__(self, name, repo)
        self._name = "{}".format(name)
        self._path = self._repo.working_dir

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_PATH: self._path,
        }

    def update(self):
        """Retrieve latest state."""
        if self._repo.bare:
            self._state = STATE_BARE
            return

        if self._repo.is_dirty(untracked_files=True):
            self._state = STATE_DIRTY
            return

        if not self._repo.active_branch.is_valid():
            self._state = STATE_INVALID
            return

        self._state = STATE_CLEAN

    def git_pull(self, remote, reset=False):
        """Pull data from a git remote."""
        from git import Remote
        git_remote = Remote(repo=self._repo, name=remote)

        if not git_remote.exists():
            _LOGGER.error("{}: Remote {} does not exist!".format(
                SERVICE_LOCAL_GIT_PULL, remote))
            return False

        if reset:
            self._repo.git.reset('--hard')

        git_remote.pull()


class GitRepoActiveBranch(GitRepoAttribute):
    """Representation of an active branch in a local Git Repo."""

    def __init__(self, name, repo):
        """Create a new local Git repo Active Branch entity."""
        GitRepoAttribute.__init__(self, name, repo)
        self._name = "{} Active Branch".format(name)

    def update(self):
        """Retrieve latest state."""
        self._state = self._repo.active_branch.name


class GitRepoActiveCommit(GitRepoAttribute):
    """Representation of an active commit in a local Git Repo."""

    def __init__(self, name, repo):
        """Create a new local Git repo Active Commit entity."""
        GitRepoAttribute.__init__(self, name, repo)
        self._name = "{} Active Commit".format(name)
        self._summary = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ACTIVE_COMMIT_SUMMARY: self._summary,
        }

    def update(self):
        """Retrieve latest state."""
        if not self._repo.active_branch.is_valid():
            self._state = STATE_INVALID
            return

        self._state = self._repo.head.commit.hexsha
        self._summary = self._repo.head.commit.summary
