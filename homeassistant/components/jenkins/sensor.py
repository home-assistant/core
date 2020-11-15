"""This component provides a HA sensor for Jenkins."""

import logging

from jenkinsapi.jenkins import Jenkins
from requests.exceptions import HTTPError

from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_USERNAME
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from .const import CONF_JOB_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Jenkins sensor based on a config entry."""
    try:
        jenkins = await hass.async_add_executor_job(
            Jenkins,
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_TOKEN],
        )
        _LOGGER.debug("Successfully connected to %s", entry.data[CONF_HOST])
    except HTTPError as exception:
        raise PlatformNotReady from exception

    [repository, branch] = entry.data[CONF_JOB_NAME].split("/", maxsplit=1)
    job = await hass.async_add_executor_job(jenkins.get_job, entry.data[CONF_JOB_NAME])
    sensor = JenkinsSensor(repository, branch, job)

    async_add_entities([sensor], True)


class JenkinsSensor(Entity):
    """Sensor for single metric in a Jenkins build."""

    def __init__(self, repository, branch, job):
        """Representation of a Jenkins sensor."""
        self.job = job
        self.repository = repository
        self.branch = branch
        self._name = f"{repository} {branch}"
        self._state = None
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return "_".join([DOMAIN, self.repository, self.branch])

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:git"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Fetch the latest build and update state."""
        last_build = self.job.get_last_build()
        self._state = last_build.get_status()

        self._attributes = {
            "Build Number": last_build.buildno,
            "Build Time": str(last_build.get_timestamp()),
            "Build Duration": str(last_build.get_duration()),
            "Jenkins build URL": last_build.get_build_url(),
            "Repository URL": last_build.get_repo_url(),
        }
