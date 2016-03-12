"""
Support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['python-nest==2.6.0']
DOMAIN = 'nest'

NEST = None


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Nest thermostat component."""
    global NEST

    logger = logging.getLogger(__name__)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    if username is None or password is None:
        logger.error("Missing required configuration items %s or %s",
                     CONF_USERNAME, CONF_PASSWORD)
        return

    import nest

    NEST = nest.Nest(username, password)

    return True
