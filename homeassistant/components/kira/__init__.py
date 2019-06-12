"""KIRA interface to receive UDP packets from an IR-IP bridge."""
import logging
import os

import voluptuous as vol
from voluptuous.error import Error as VoluptuousError
import yaml

from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SENSORS, CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN, CONF_CODE)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

DOMAIN = 'kira'

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 65432

CONF_REPEAT = "repeat"
CONF_REMOTES = "remotes"
CONF_SENSOR = "sensor"
CONF_REMOTE = "remote"

CODES_YAML = '{}_codes.yaml'.format(DOMAIN)

CODE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_CODE): cv.string,
    vol.Optional(CONF_TYPE): cv.string,
    vol.Optional(CONF_DEVICE): cv.string,
    vol.Optional(CONF_REPEAT): cv.positive_int,
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DOMAIN):
        vol.Exclusive(cv.string, "sensors"),
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

REMOTE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DOMAIN):
        vol.Exclusive(cv.string, "remotes"),
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_SENSORS): [SENSOR_SCHEMA],
        vol.Optional(CONF_REMOTES): [REMOTE_SCHEMA]})
}, extra=vol.ALLOW_EXTRA)


def load_codes(path):
    """Load KIRA codes from specified file."""
    codes = []
    if os.path.exists(path):
        with open(path) as code_file:
            data = yaml.load(code_file) or []
        for code in data:
            try:
                codes.append(CODE_SCHEMA(code))
            except VoluptuousError as exception:
                # keep going
                _LOGGER.warning("KIRA code invalid data: %s", exception)
    else:
        with open(path, 'w') as code_file:
            code_file.write('')
    return codes


def setup(hass, config):
    """Set up the KIRA component."""
    import pykira

    sensors = config.get(DOMAIN, {}).get(CONF_SENSORS, [])
    remotes = config.get(DOMAIN, {}).get(CONF_REMOTES, [])
    # If no sensors or remotes were specified, add a sensor
    if not(sensors or remotes):
        sensors.append({})

    codes = load_codes(hass.config.path(CODES_YAML))

    hass.data[DOMAIN] = {
        CONF_SENSOR: {},
        CONF_REMOTE: {},
    }

    def load_module(platform, idx, module_conf):
        """Set up the KIRA module and load platform."""
        # note: module_name is not the HA device name. it's just a unique name
        # to ensure the component and platform can share information
        module_name = ("%s_%d" % (DOMAIN, idx)) if idx else DOMAIN
        device_name = module_conf.get(CONF_NAME, DOMAIN)
        port = module_conf.get(CONF_PORT, DEFAULT_PORT)
        host = module_conf.get(CONF_HOST, DEFAULT_HOST)

        if platform == CONF_SENSOR:
            module = pykira.KiraReceiver(host, port)
            module.start()
        else:
            module = pykira.KiraModule(host, port)

        hass.data[DOMAIN][platform][module_name] = module
        for code in codes:
            code_tuple = (code.get(CONF_NAME),
                          code.get(CONF_DEVICE, STATE_UNKNOWN))
            module.registerCode(code_tuple, code.get(CONF_CODE))

        discovery.load_platform(hass, platform, DOMAIN,
                                {'name': module_name, 'device': device_name},
                                config)

    for idx, module_conf in enumerate(sensors):
        load_module(CONF_SENSOR, idx, module_conf)

    for idx, module_conf in enumerate(remotes):
        load_module(CONF_REMOTE, idx, module_conf)

    def _stop_kira(_event):
        """Stop the KIRA receiver."""
        for receiver in hass.data[DOMAIN][CONF_SENSOR].values():
            receiver.stop()
        _LOGGER.info("Terminated receivers")

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_kira)

    return True
