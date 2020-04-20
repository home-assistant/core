"""Integration for Jenkins."""

import logging

from jenkinsapi.jenkins import Jenkins
import voluptuous as vol

from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

DOMAIN = "jenkins"
_LOGGER = logging.getLogger(__name__)

# Configuration keys
CONF_REPOSITORY = "repository"
CONF_BRANCH = "branch"

# Default values
DEFAULT_BRANCH = "master"

# Validating configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.string,
                vol.Required(CONF_REPOSITORY): cv.string,
                vol.Optional(CONF_BRANCH, default=DEFAULT_BRANCH): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Jenkins integration."""

    hass.states.set("jenkins.repo", config[DOMAIN].get(CONF_REPOSITORY))
    hass.states.set("jenkins.branch", config[DOMAIN].get(CONF_BRANCH))

    _LOGGER.debug(f"repo: {config[DOMAIN].get(CONF_URL)}")
    _LOGGER.debug(f"repo: {config[DOMAIN].get(CONF_REPOSITORY)}")
    _LOGGER.debug(f"branch: {config[DOMAIN].get(CONF_BRANCH)}")

    server = Jenkins(config[DOMAIN].get(CONF_URL))
    for (job_name, job) in server.get_jobs():
        _LOGGER.debug(f"Job name: {job_name}")

    return True
