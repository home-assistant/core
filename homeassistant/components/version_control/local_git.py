"""
Support for monitoring a local git repository.

Creates entities that breakout information about
the specified local git repository.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/version_control.local_git/
"""
import logging

import voluptuous as vol
from homeassistant.components.version_control import (
    ATTR_BRANCH_NAME, ATTR_COMMIT_TITLE, DOMAIN, PLATFORM_SCHEMA)

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_NAME, CONF_PATH, STATE_PROBLEM, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['gitpython==2.1.9']

_LOGGER = logging.getLogger(__name__)

ATTR_PATH = 'path'
ATTR_STATUS = 'status'
ATTR_REMOTE = 'remote'
ATTR_RESET = 'reset'
ATTR_ACTIVE_COMMIT_SUMMARY = 'commit_summary'

DATA_LOCAL_GIT = 'local_git'

SERVICE_LOCAL_GIT_PULL = 'local_git_pull'

STATUS_BARE = 'bare'
STATUS_CLEAN = 'clean'
STATUS_DIRTY = 'dirty'
STATUS_INVALID = 'invalid'

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
    from git import exc as git_exceptions

    if hass.data.get(DATA_LOCAL_GIT) is None:
        hass.data[DATA_LOCAL_GIT] = []

    entities = []

    try:
        local_git_repo = GitRepo(
            name=config.get(CONF_NAME),
            repo=Repo(config.get(CONF_PATH))
        )
    except git_exceptions.NoSuchPathError:
        _LOGGER.error("No such path: {}", config.get(CONF_PATH))
        return False
    except git_exceptions.InvalidGitRepositoryError:
        _LOGGER.error("No Git repository found in {}", config.get(CONF_PATH))
        return False

    entities.append(local_git_repo)

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

        self._commit_title = None
        self._branch_name = None
        self._commit_title = None
        self._status = None
        self._state = STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_PATH: self._path,
            ATTR_STATUS: self._status
        }

        # Add additional attributes.
        if self._branch_name is not None:
            attributes[ATTR_BRANCH_NAME] = self._branch_name

        if self._commit_title is not None:
            attributes[ATTR_COMMIT_TITLE] = self._commit_title

        return attributes

    def update(self):
        """Retrieve latest state."""
        if self._repo.bare:
            self._status = STATUS_BARE
            self._state = STATE_PROBLEM
            return

        self._branch_name = self._repo.active_branch.name

        if not self._repo.active_branch.is_valid():
            self._status = STATUS_INVALID
            self._state = STATE_PROBLEM
            return

        if self._repo.is_dirty(untracked_files=True):
            self._status = STATUS_DIRTY
        else:
            self._status = STATUS_CLEAN

        try:
            self._state = self._repo.head.commit.hexsha
        except ValueError:
            self._state = STATE_UNKNOWN

        try:
            self._commit_title = self._repo.head.commit.summary
        except ValueError:
            self._commit_title = None

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
