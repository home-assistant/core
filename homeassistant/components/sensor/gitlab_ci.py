import requests
import json
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_TOKEN, CONF_SCAN_INTERVAL, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN)

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

# SENSOR_TYPES = {
#   'last_build_id': ['Last Build ID', '', 'mdi:account-card-details'],
#   'last_build_state': ['Last Build State', '', 'mdi:thumbs-up-down'],
#   'last_build_started_at': ['Last Build Started At', '', 'mdi:timetable'],
#   'last_build_finished_at': ['Last Build Finished At', '', 'mdi:timetable'],
#   'last_build_duration': ['Last Build Duration', 'sec', 'mdi:timelapse'],
#   'last_commit_id': ['Last Commit ID', '', 'mdi:account-card-details'],
#   'last_commit_date': ['Last Commit Date', '', 'mdi:timetable'],
#   'last_build_branch': ['Last Build Branch', '', 'mdi:thumbs-up-down'],
#   'state': ['State', '', 'mdi:thumbs-up-down']
# }

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_GITLAB_ID): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    logger = logging.getLogger(__name__)
    
    priv_token = config.get(CONF_TOKEN)
    gitlab_id = config.get(CONF_GITLAB_ID)
    SCAN_INTERVAL = config.get(CONF_SCAN_INTERVAL)
    
    if priv_token is None:
        logger.error('No private access token specified')
        return False
    if gitlab_id is None:
        logger.error('No GitLab ID specified')
        return False
      
    add_devices([GitLabSensor(gitlab_id, priv_token)])

class GitLabSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, gitlab_id, priv_token):
        """Initialize the sensor."""
        self._gitlab_id = gitlab_id
        self._private_access_token = {'PRIVATE-TOKEN': priv_token}
        self._url = "https://gitlab.com/api/v4/projects/" + self._gitlab_id + "/jobs?per_page=1&page=1"
        self._state = None
        
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
        elif self._status == 'failed':
          return ICON_SAD
        else:
          return ICON_OTHER


        
    @Throttle(SCAN_INTERVAL)
    def update(self):
        logger = logging.getLogger(__name__)
        logger.info(SCAN_INTERVAL)
        self._response = requests.get(self._url, headers=self._private_access_token).text[1:-1]
        try:
          self._response_json = json.loads(self._response)
          self._status = self._response_json['status']
          self._started_at = self._response_json['started_at']
          self._finished_at = self._response_json['finished_at']
          self._duration = self._response_json['duration']
          self._commit_id = self._response_json['commit']['id']
          self._commit_date = self._response_json['commit']['committed_date']
          self._build_id = self._response_json['id']
          self._branch = self._response_json['ref']
          self._state = self._status
        except:
          self._status = STATE_UNKNOWN
          self._started_at = ''
          self._finished_at = ''
          self._duration = ''
          self._commit_id = ''
          self._commit_date = ''
          self._build_id = ''
          self._branch = ''
          self._state = self._status
        