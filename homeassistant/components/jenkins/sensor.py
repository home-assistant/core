"""This component provides a HA sensor for Jenkins."""


from jenkinsapi.custom_exceptions import UnknownJob
from jenkinsapi.jenkins import Jenkins
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import _LOGGER

# Configuration keys
CONF_REPOSITORY = "repository"
CONF_BRANCH = "branch"

# Default values
DEFAULT_BRANCH = "master"

# Validating configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_REPOSITORY): cv.string,
        vol.Optional(CONF_BRANCH, default=DEFAULT_BRANCH): cv.string,
    },
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the configured sensors."""

    jenkins_url = config.get(CONF_URL)
    repository = config.get(CONF_REPOSITORY)
    branch = config.get(CONF_BRANCH)

    try:
        server = Jenkins(jenkins_url)
        _LOGGER.debug(f"Successfully connected to {jenkins_url}")
    except HTTPError:
        _LOGGER.error(
            f"Could not connect to {jenkins_url}. Is the specified URL correct?"
        )
        return False

    # Fetch the configured jobs and add as sensors
    sensors = []
    try:
        job = server.get_job(f"{repository}/{branch}")
        sensors.append(JenkinsSensor(repository, branch, job))
        _LOGGER.debug(f"Added sensor for {repository}/{branch}")
    except UnknownJob:
        _LOGGER.error(
            f'Could not find a job for repository "{repository}" and branch "{branch}". Is there a job with at least one build for this on {jenkins_url}?'
        )

    add_entities(sensors, True)

    return True


class JenkinsSensor(Entity):
    """Sensor for single metric in a Jenkins build."""

    def __init__(self, repository, branch, job):
        """Representation of a Jenkins sensor."""
        self.job = job
        self.repository = repository
        self.branch = branch
        self._name = f"{repository} {branch}"
        self._unique_id = f"{self.repository}_{self.branch}"
        self._state = None
        self._attributes = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

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
