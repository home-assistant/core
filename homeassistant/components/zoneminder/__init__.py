"""
Support for ZoneMinder.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PATH, CONF_SSL, CONF_USERNAME,
    CONF_VERIFY_SSL, ATTR_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['zm-py==0.3.0']

CONF_PATH_ZMS = 'path_zms'

DEFAULT_PATH = '/zm/'
DEFAULT_PATH_ZMS = '/zm/cgi-bin/nph-zms'
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DOMAIN = 'zoneminder'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_SET_RUN_STATE = 'set_run_state'
SET_RUN_STATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string
})


def setup(hass, config):
    """Set up the ZoneMinder component."""
    from zoneminder.zm import ZoneMinder

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    hass.data[DOMAIN] = ZoneMinder(server_origin,
                                   conf.get(CONF_USERNAME),
                                   conf.get(CONF_PASSWORD),
                                   conf.get(CONF_PATH),
                                   conf.get(CONF_PATH_ZMS),
                                   conf.get(CONF_VERIFY_SSL))

    def set_active_state(call):
        """Set the ZoneMinder run state to the given state name."""
        return hass.data[DOMAIN].set_active_state(call.data[ATTR_NAME])

    hass.services.register(
        DOMAIN, SERVICE_SET_RUN_STATE, set_active_state,
        schema=SET_RUN_STATE_SCHEMA
    )

    return hass.data[DOMAIN].login()
