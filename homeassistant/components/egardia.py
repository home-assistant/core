"""
Interfaces with Egardia/Woonveilig alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/egardia/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PORT, CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME,
    EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['pythonegardia==1.0.38']

_LOGGER = logging.getLogger(__name__)

CONF_REPORT_SERVER_CODES = 'report_server_codes'
CONF_REPORT_SERVER_ENABLED = 'report_server_enabled'
CONF_REPORT_SERVER_PORT = 'report_server_port'
REPORT_SERVER_CODES_IGNORE = 'ignore'
CONF_VERSION = 'version'

DEFAULT_NAME = 'Egardia'
DEFAULT_PORT = 80
DEFAULT_REPORT_SERVER_ENABLED = False
DEFAULT_REPORT_SERVER_PORT = 52010
DEFAULT_VERSION = 'GATE-01'
DOMAIN = 'egardia'
EGARDIA_SERVER = 'egardia_server'
EGARDIA_DEVICE = 'egardiadevice'
EGARDIA_NAME = 'egardianame'
EGARDIA_REPORT_SERVER_ENABLED = 'egardia_rs_enabled'
EGARDIA_REPORT_SERVER_CODES = 'egardia_rs_codes'
NOTIFICATION_ID = 'egardia_notification'
NOTIFICATION_TITLE = 'Egardia'
ATTR_DISCOVER_DEVICES = 'egardia_sensor'

SERVER_CODE_SCHEMA = vol.Schema({
    vol.Optional('arm'): vol.All(cv.ensure_list_csv, [cv.string]),
    vol.Optional('disarm'): vol.All(cv.ensure_list_csv, [cv.string]),
    vol.Optional('armhome'): vol.All(cv.ensure_list_csv, [cv.string]),
    vol.Optional('triggered'): vol.All(cv.ensure_list_csv, [cv.string]),
    vol.Optional('ignore'): vol.All(cv.ensure_list_csv, [cv.string])
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_REPORT_SERVER_CODES, default={}): SERVER_CODE_SCHEMA,
        vol.Optional(CONF_REPORT_SERVER_ENABLED,
                     default=DEFAULT_REPORT_SERVER_ENABLED): cv.boolean,
        vol.Optional(CONF_REPORT_SERVER_PORT,
                     default=DEFAULT_REPORT_SERVER_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Egardia platform."""
    from pythonegardia import egardiadevice
    from pythonegardia import egardiaserver
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    version = conf.get(CONF_VERSION)
    rs_enabled = conf.get(CONF_REPORT_SERVER_ENABLED)
    rs_port = conf.get(CONF_REPORT_SERVER_PORT)
    try:
        device = hass.data[EGARDIA_DEVICE] = egardiadevice.EgardiaDevice(
            host, port, username, password, '', version)
    except requests.exceptions.RequestException:
        _LOGGER.error("An error occurred accessing your Egardia device. " +
                      "Please check config.")
        return False
    except egardiadevice.UnauthorizedError:
        _LOGGER.error("Unable to authorize. Wrong password or username.")
        return False
    # Set up the egardia server if enabled
    if rs_enabled:
        _LOGGER.debug("Setting up EgardiaServer")
        try:
            if EGARDIA_SERVER not in hass.data:
                server = egardiaserver.EgardiaServer('', rs_port)
                bound = server.bind()
                if not bound:
                    raise IOError("Binding error occurred while " +
                                  "starting EgardiaServer.")
                hass.data[EGARDIA_SERVER] = server
                server.start()

            def handle_stop_event(event):
                """Callback function for HA stop event."""
                server.stop()

            # listen to home assistant stop event
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop_event)

        except IOError:
            _LOGGER.error("Binding error occurred while starting " +
                          "EgardiaServer.")
            return False

    discovery.load_platform(hass, 'alarm_control_panel', DOMAIN,
                            discovered=conf, hass_config=config)

    # get the sensors from the device and add those
    sensors = device.getsensors()
    discovery.load_platform(hass, 'binary_sensor', DOMAIN,
                            {ATTR_DISCOVER_DEVICES: sensors}, config)

    return True
