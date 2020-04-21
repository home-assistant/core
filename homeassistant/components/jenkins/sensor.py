"""This component provides a HA sensor for Jenkins."""


from jenkinsapi.custom_exceptions import UnknownJob
from jenkinsapi.jenkins import Jenkins
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

    _LOGGER.debug(f"url: {jenkins_url}")
    _LOGGER.debug(f"repo: {repository}")
    _LOGGER.debug(f"branch: {branch}")

    server = Jenkins(jenkins_url)

    sensors = []

    # Fetch the configured jobs and add as sensors
    try:
        job = server.get_job(f"{repository}/{branch}")
        sensors.append(JenkinsSensor(repository, branch, job))
    except UnknownJob:
        _LOGGER.error(
            f'Could not find a job for repository "{repository}" and branch "{branch}".'
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
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch the latest build and update state."""
        last_build = self.job.get_last_build()
        self._state = last_build.get_status()
