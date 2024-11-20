"""Sensor for retrieving latest GitLab CI job information."""

from __future__ import annotations

from datetime import timedelta
import logging

from gitlab import Gitlab, GitlabAuthenticationError, GitlabGetError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_BUILD_BRANCH = "build branch"
ATTR_BUILD_COMMIT_DATE = "commit date"
ATTR_BUILD_COMMIT_ID = "commit id"
ATTR_BUILD_DURATION = "build_duration"
ATTR_BUILD_FINISHED = "build_finished"
ATTR_BUILD_ID = "build id"
ATTR_BUILD_STARTED = "build_started"
ATTR_BUILD_STATUS = "build_status"
ATTRIBUTION = "Information provided by https://gitlab.com/"

CONF_GITLAB_ID = "gitlab_id"

DEFAULT_NAME = "GitLab CI Status"
DEFAULT_URL = "https://gitlab.com"

ICON_HAPPY = "mdi:emoticon-happy"
ICON_OTHER = "mdi:git"
ICON_SAD = "mdi:emoticon-sad"

SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_GITLAB_ID): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_URL, default=DEFAULT_URL): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GitLab sensor platform."""
    _name = config.get(CONF_NAME, DEFAULT_NAME)
    _interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    _url = config.get(CONF_URL)

    _gitlab_data = GitLabData(
        priv_token=config[CONF_TOKEN],
        gitlab_id=config[CONF_GITLAB_ID],
        interval=_interval,
        url=_url,
    )

    add_entities([GitLabSensor(_gitlab_data, _name)], True)


class GitLabSensor(SensorEntity):
    """Representation of a GitLab sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, gitlab_data: GitLabData, name: str) -> None:
        """Initialize the GitLab sensor."""
        self._attr_available = False
        self._gitlab_data = gitlab_data
        self._attr_name = name

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.native_value == "success":
            return ICON_HAPPY
        if self.native_value == "failed":
            return ICON_SAD
        return ICON_OTHER

    def update(self) -> None:
        """Collect updated data from GitLab API."""
        self._gitlab_data.update()

        self._attr_native_value = self._gitlab_data.status
        self._attr_extra_state_attributes = {
            ATTR_BUILD_STATUS: self._gitlab_data.status,
            ATTR_BUILD_STARTED: self._gitlab_data.started_at,
            ATTR_BUILD_FINISHED: self._gitlab_data.finished_at,
            ATTR_BUILD_DURATION: self._gitlab_data.duration,
            ATTR_BUILD_COMMIT_ID: self._gitlab_data.commit_id,
            ATTR_BUILD_COMMIT_DATE: self._gitlab_data.commit_date,
            ATTR_BUILD_ID: self._gitlab_data.build_id,
            ATTR_BUILD_BRANCH: self._gitlab_data.branch,
        }
        self._attr_available = self._gitlab_data.available


class GitLabData:
    """GitLab Data object."""

    def __init__(self, gitlab_id, priv_token, interval, url):
        """Fetch data from GitLab API for most recent CI job."""

        self._gitlab_id = gitlab_id
        self._gitlab = Gitlab(url, private_token=priv_token, per_page=1)
        self._gitlab.auth()
        self.update = Throttle(interval)(self._update)

        self.available = False
        self.status = None
        self.started_at = None
        self.finished_at = None
        self.duration = None
        self.commit_id = None
        self.commit_date = None
        self.build_id = None
        self.branch = None

    def _update(self) -> None:
        try:
            _projects = self._gitlab.projects.get(self._gitlab_id)
            _last_pipeline = _projects.pipelines.list(page=1)[0]
            _last_job = _last_pipeline.jobs.list(page=1)[0]
            self.status = _last_pipeline.attributes.get("status")
            self.started_at = _last_job.attributes.get("started_at")
            self.finished_at = _last_job.attributes.get("finished_at")
            self.duration = _last_job.attributes.get("duration")
            _commit = _last_job.attributes.get("commit")
            self.commit_id = _commit.get("id")
            self.commit_date = _commit.get("committed_date")
            self.build_id = _last_job.attributes.get("id")
            self.branch = _last_job.attributes.get("ref")
            self.available = True
        except GitlabAuthenticationError as erra:
            _LOGGER.error("Authentication Error: %s", erra)
            self.available = False
        except GitlabGetError as errg:
            _LOGGER.error("Project Not Found: %s", errg)
            self.available = False
