"""Support for Zabbix."""
import logging
from urllib.parse import urljoin

import voluptuous as vol

from homeassistant.const import (
    CONF_PATH, CONF_HOST, CONF_SSL, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_PATH = 'zabbix'
DOMAIN = 'zabbix'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Zabbix component."""
    from pyzabbix import ZabbixAPI, ZabbixAPIException

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    url = urljoin('{}://{}'.format(schema, conf[CONF_HOST]), conf[CONF_PATH])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    zapi = ZabbixAPI(url)
    try:
        zapi.login(username, password)
        _LOGGER.info("Connected to Zabbix API Version %s", zapi.api_version())
    except ZabbixAPIException as login_exception:
        _LOGGER.error("Unable to login to the Zabbix API: %s", login_exception)
        return False

    hass.data[DOMAIN] = zapi
    return True
