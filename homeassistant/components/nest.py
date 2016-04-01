"""
Support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['python-nest==2.6.0']
DOMAIN = 'nest'

NEST = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str
    })
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Nest thermostat component."""
    global NEST

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    import nest

    NEST = nest.Nest(username, password)

    return True
