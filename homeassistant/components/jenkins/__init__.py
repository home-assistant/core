"""Integration for Jenkins."""

import logging

import voluptuous as vol

# from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

# from homeassistant.const import (
#     ATTR_ATTRIBUTION,
#     CONF_API_KEY,
#     CONF_MONITORED_CONDITIONS,
#     CONF_SCAN_INTERVAL,
#     TIME_SECONDS,
# )

DOMAIN = "jenkins"
_LOGGER = logging.getLogger(__name__)

# Configuration keys
CONF_REPOSITORY = "repository"
CONF_BRANCH = "branch"

# Default values
DEFAULT_BRANCH_NAME = "master"


# Validating configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_REPOSITORY): cv.string,
                vol.Optional(CONF_BRANCH, default=DEFAULT_BRANCH_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Jenkins integration."""

    hass.states.set("jenkins.dummy", "Jacob")
    hass.states.set("jenkins.repo", config[DOMAIN].get(CONF_REPOSITORY))
    hass.states.set("jenkins.branch", config[DOMAIN].get(CONF_BRANCH))

    _LOGGER.debug("repo: %s" % (config[DOMAIN].get(CONF_REPOSITORY)))
    _LOGGER.debug("branch: %s" % (config[DOMAIN].get(CONF_BRANCH)))

    return True
