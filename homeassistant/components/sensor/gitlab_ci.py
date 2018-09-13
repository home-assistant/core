"""Module for retrieving latest GitLab CI job information."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

CONF_GITLAB_ID = 'gitlab_id'
CONF_ATTRIBUTION = "Information provided by https://gitlab.com/"

ICON_HAPPY = 'mdi:emoticon-happy'
ICON_SAD = 'mdi:emoticon-happy'
ICON_OTHER = 'mdi:git'

ATTR_BUILD_ID = 'build id'
ATTR_BUILD_STATUS = 'build_status'
ATTR_BUILD_STARTED = 'build_started'
ATTR_BUILD_FINISHED = 'build_finished'
ATTR_BUILD_DURATION = 'build_duration'
ATTR_BUILD_COMMIT_ID = 'commit id'
ATTR_BUILD_COMMIT_DATE = 'commit date'
ATTR_BUILD_BRANCH = 'master'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_GITLAB_ID): cv.string,
    vol.Optional(CONF_URL, default='https://gitlab.com'): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL,
                 default=timedelta(seconds=300)): cv.time_period,
})

REQUIREMENTS = ['python-gitlab==1.6.0']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sensor platform setup."""
    _logger = logging.getLogger(__name__)

    _priv_token = config.get(CONF_TOKEN)
    _gitlab_id = config.get(CONF_GITLAB_ID)
    _interval = config.get(CONF_SCAN_INTERVAL)
    _url = config.get(CONF_URL)

    if _priv_token is None:
        _logger.error('No private access token specified')
        return False
    if _gitlab_id is None:
        _logger.error('No GitLab ID specified')
        return False

    _gitlab_data = GitLabData(
        priv_token=_priv_token,
        gitlab_id=_gitlab_id,
        interval=_interval,
        url=_url
    )

    add_devices([GitLabSensor(_gitlab_id, _priv_token, _gitlab_data)])


class GitLabSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, gitlab_id, priv_token, gitlab_data):
        """Initialize the sensor."""
        self._state = None
        self._gitlab_data = gitlab_data
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'GitLab CI Status'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        pass

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_BUILD_STATUS: self._status,
            ATTR_BUILD_STARTED: self._started_at,
            ATTR_BUILD_FINISHED: self._finished_at,
            ATTR_BUILD_DURATION: self._duration,
            ATTR_BUILD_COMMIT_ID: self._commit_id,
            ATTR_BUILD_COMMIT_DATE: self._commit_date,
            ATTR_BUILD_ID: self._build_id,
            ATTR_BUILD_BRANCH: self._branch
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self._status == 'success':
            return ICON_HAPPY
        if self._status == 'failed':
            return ICON_SAD
        return ICON_OTHER

    def update(self):
        """Collect updated data from GitLab API."""
        self._gitlab_data.update()

        self._status = self._gitlab_data.status
        self._started_at = self._gitlab_data.started_at
        self._finished_at = self._gitlab_data.finished_at
        self._duration = self._gitlab_data.duration
        self._commit_id = self._gitlab_data.commit_id
        self._commit_date = self._gitlab_data.commit_date
        self._build_id = self._gitlab_data.build_id
        self._branch = self._gitlab_data.branch
        self._state = self._gitlab_data.status


class GitLabData():
    """GitLab Data object."""

    def __init__(self, gitlab_id, priv_token, interval, url):
        """Fetch data from GitLab API for most recent CI job."""
        self._gitlab_id = gitlab_id
        self._priv_token = priv_token
        self._interval = interval
        self._url = url
        self.update = Throttle(interval)(self._update)

        self._response = None
        self._response_json = None
        self.available = False
        self.status = STATE_UNKNOWN
        self.started_at = STATE_UNKNOWN
        self.finished_at = STATE_UNKNOWN
        self.duration = STATE_UNKNOWN
        self.commit_id = STATE_UNKNOWN
        self.commit_date = STATE_UNKNOWN
        self.build_id = STATE_UNKNOWN
        self.branch = STATE_UNKNOWN
        self.state = STATE_UNKNOWN

    def _update(self):
        _logger = logging.getLogger(__name__)
        _logger.debug(self._interval)
        import gitlab
        import requests
        try:
            _gitlab = gitlab.Gitlab(self._url, private_token=self._priv_token)
            _gitlab.auth()
            _projects = _gitlab.projects.get(self._gitlab_id)
            _last_pipeline = _projects.pipelines.list()[0]
            _last_job = _last_pipeline.jobs.list()[0]
            self.available = True
            self.status = _last_pipeline.attributes['status']
            self.started_at = _last_job['started_at']
            self.finished_at = _last_job['finished_at']
            self.duration = _last_job['duration']
            self.commit_id = _last_job['commit']['id']
            self.commit_date = _last_job['commit']['committed_date']
            self.build_id = _last_job['id']
            self.branch = _last_job['ref']
            self.state = self.status
        except gitlab.exceptions.GitlabAuthenticationError as erra:
            _logger.error("Authentication Error: %s", erra)
            self.available = False
        except gitlab.exceptions.GitlabGetError as errg:
            _logger.error("Project Not Found: %s", errg)
            self.available = False
        except requests.exceptions.ConnectionError as errc:
            _logger.error("Error Connecting: %s", errc)
            self.available = False
