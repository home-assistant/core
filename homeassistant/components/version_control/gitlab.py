"""
Support for monitoring a remote Gitlab git repository.

Creates entities that breakout information about
the specified repository.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/version_control.gitlab/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.version_control import (
    ATTR_BRANCH_NAME, ATTR_COMMIT_TITLE, PLATFORM_SCHEMA,
    VersionControlException)
from homeassistant.const import (
    CONF_NAME, CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-gitlab==1.4.0']

_LOGGER = logging.getLogger(__name__)

ATTR_PIPELINE_STATUS = 'pipeline_status'
ATTR_PROJECT = 'project'

CONF_BRANCH = 'branch'
CONF_PROJECT = 'project'

DATA_GITLAB = 'gitlab'

DEFAULT_GITLAB_BRANCH = 'master'
DEFAULT_GITLAB_URL = 'https://gitlab.com'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_PROJECT): cv.string,
    vol.Optional(CONF_BRANCH, default=DEFAULT_GITLAB_BRANCH): cv.string,
    vol.Optional(CONF_URL, default=DEFAULT_GITLAB_URL): cv.url,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Git repository sensor."""
    if hass.data.get(DATA_GITLAB) is None:
        hass.data[DATA_GITLAB] = []

    entities = []

    try:
        gitlab_data = GitlabData(
            url=config.get(CONF_URL),
            token=config.get(CONF_TOKEN),
            verify_ssl=config.get(CONF_VERIFY_SSL),
            project=config.get(CONF_PROJECT),
            branch=config.get(CONF_BRANCH)
        )
    except VersionControlException as error:
        _LOGGER.error(error)
        return False

    gitlab_repo = GitlabRepo(
        name=config.get(CONF_NAME), gitlab_data=gitlab_data
    )

    entities.append(gitlab_repo)

    hass.data[DATA_GITLAB].append(gitlab_repo)
    add_entities(entities, update_before_add=True)


class GitlabRepo(Entity):
    """Representation of Gitlab repo entity."""

    def __init__(self, name, gitlab_data):
        """Create a new local Git repo attribute."""
        self._branch_name = None
        self._commit_title = None
        self._name = name
        self._old_value = None
        self._pipeline_status = None
        self._project_name = None
        self._state = STATE_UNKNOWN
        self.gitlab_data = gitlab_data

    @property
    def should_poll(self):
        """Polling is needed."""
        return True

    @property
    def name(self):
        """Return the name of the Gitlab repo entity."""
        return self._name

    @property
    def state(self):
        """Return attribute state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_PROJECT: self._project_name,
            ATTR_BRANCH_NAME: self._branch_name,
            ATTR_COMMIT_TITLE: self._commit_title
        }

        # Add additional attributes.
        if self._pipeline_status is not None:
            attributes[ATTR_PIPELINE_STATUS] = self._pipeline_status

        return attributes

    def update(self):
        """Get the latest data from Gitlab and updates the state."""
        # Call the API for new data. Each sensor will re-trigger this
        # same exact call, but that's fine. Results should be cached for
        # a short period of time to prevent hitting API limits.
        self.gitlab_data.update()

        if self.gitlab_data.project is not None:
            self._project_name = self.gitlab_data.project.attributes[
                'path_with_namespace']

        if self.gitlab_data.branch is not None:
            self._state = self.gitlab_data.branch.commit['id']
            self._commit_title = self.gitlab_data.branch.commit['title']
            self._branch_name = self.gitlab_data.branch.name

        if self.gitlab_data.pipeline is not None:
            self._pipeline_status = self.gitlab_data.pipeline.status


class GitlabData(object):
    """Gets the latest project data from Gitlab."""

    def __init__(self, url, token, verify_ssl, project, branch):
        """Initialize the data object."""
        self._url = url
        self._token = token
        self._verify_ssl = verify_ssl
        self._project = project
        self._branch = branch

        self.project = None
        self.branch = None
        self.pipeline = None

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Gitlab."""
        from gitlab import Gitlab
        from gitlab import exceptions as gitlab_exceptions

        try:
            with Gitlab(
                    url=self._url,
                    private_token=self._token,
                    ssl_verify=self._verify_ssl
            ) as gitlab:
                self.project = gitlab.projects.get(id=self._project)

        except (gitlab_exceptions.GitlabGetError,
                gitlab_exceptions.GitlabAuthenticationError) as error:
            raise VersionControlException(
                "Unable to init Gitlab project {}, {}".format(
                    self._project, str(error.error_message))
            )

        try:
            self.branch = self.project.branches.get(
                id=self._branch
            )
        except gitlab_exceptions.GitlabGetError as error:
            raise VersionControlException(
                "Unable to load branch {}: {}".format(
                    self._branch, str(error.error_message))
            )

        if self.branch is not None:
            branch_pipelines = self.project.pipelines.list(
                ref=self._branch,
                order_by='id',
                sort='desc'
            )

            if len(branch_pipelines) > 0:
                self.pipeline = branch_pipelines[0]
