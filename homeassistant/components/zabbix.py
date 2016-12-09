"""
Support for Zabbix.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zabbix/
"""
import logging
from urllib.parse import urljoin

import voluptuous as vol

from homeassistant.const import (
    CONF_PATH, CONF_HOST, CONF_SSL, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyzabbix==0.7.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_PATH = "zabbix"

DOMAIN = 'zabbix'

ZAPI = None


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Zabbix component."""
    from pyzabbix import ZabbixAPI

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    url = urljoin('{}://{}'.format(schema, conf[CONF_HOST]), conf[CONF_PATH])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    global ZAPI
    ZAPI = ZabbixAPI(url)
    ZAPI.login(username, password)
    _LOGGER.info("Connected to Zabbix API Version %s", ZAPI.api_version())

    return True
