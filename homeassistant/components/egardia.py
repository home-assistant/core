"""
Interfaces with Egardia/Woonveilig alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/egardia/
"""
import logging

import requests
import voluptuous as vol

import homeassistant.exceptions as exc
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PORT, CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN,
    CONF_NAME, STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_TRIGGERED, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['pythonegardia==1.0.36']

_LOGGER = logging.getLogger(__name__)

CONF_REPORT_SERVER_CODES = 'report_server_codes'
CONF_REPORT_SERVER_ENABLED = 'report_server_enabled'
CONF_REPORT_SERVER_PORT = 'report_server_port'
CONF_REPORT_SERVER_CODES_IGNORE = 'ignore'
CONF_VERSION = 'version'

DEFAULT_NAME = 'Egardia'
DEFAULT_PORT = 80
DEFAULT_REPORT_SERVER_ENABLED = False
DEFAULT_REPORT_SERVER_PORT = 52010
DEFAULT_VERSION = 'GATE-01'
DOMAIN = 'egardia'
D_EGARDIASRV = 'egardiaserver'
D_EGARDIASYS = 'egardiadevice'
D_EGARDIANM = 'egardianame'
D_EGARDIARSENABLED = 'egardia_rs_enabled'
D_EGARDIARSCODES = 'egardia_rs_codes'
D_EGARDIADEV = 'egardia_dev'
NOTIFICATION_ID = 'egardia_notification'
NOTIFICATION_TITLE = 'Egardia'
ATTR_DISCOVER_DEVICES = 'egardia_sensor'
STATES = {
    'ARM': STATE_ALARM_ARMED_AWAY,
    'DAY HOME': STATE_ALARM_ARMED_HOME,
    'DISARM': STATE_ALARM_DISARMED,
    'HOME': STATE_ALARM_ARMED_HOME,
    'TRIGGERED': STATE_ALARM_TRIGGERED,
    'UNKNOWN': STATE_UNKNOWN,
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_REPORT_SERVER_CODES): vol.All(cv.ensure_list),
        vol.Optional(CONF_REPORT_SERVER_ENABLED,
                     default=DEFAULT_REPORT_SERVER_ENABLED): cv.boolean,
        vol.Optional(CONF_REPORT_SERVER_PORT,
                     default=DEFAULT_REPORT_SERVER_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Egardia platform."""
    from pythonegardia import egardiadevice
    domainconf = config[DOMAIN]
    username = domainconf.get(CONF_USERNAME)
    password = domainconf.get(CONF_PASSWORD)
    host = domainconf.get(CONF_HOST)
    port = domainconf.get(CONF_PORT)
    version = domainconf.get(CONF_VERSION)
    try:
        device = hass.data[D_EGARDIASYS] = egardiadevice.EgardiaDevice(
            host, port, username, password, '', version)
    except requests.exceptions.RequestException:
        raise exc.PlatformNotReady()
    except egardiadevice.UnauthorizedError:
        _LOGGER.error("Unable to authorize. Wrong password or username")
        return

    discovery.load_platform(hass, 'alarm_control_panel', DOMAIN,
                            discovered=domainconf, hass_config=config)

    def handle_stop_event(event):
        """Callback function for HA stop event."""
        hass.data[D_EGARDIASRV].stop()

    # listen to home assistant stop event
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop_event)

    # get the sensors from the device and add those
    sensors = device.getsensors()
    discovery.load_platform(hass, 'binary_sensor', DOMAIN,
                            {ATTR_DISCOVER_DEVICES: sensors}, config)

    return True
