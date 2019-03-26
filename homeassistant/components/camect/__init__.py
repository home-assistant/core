"""
Support for Camect Home.

Example configuration.yaml entry:
camect:
    host: camect.local
    port: 8443
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    camera_ids: aaa,bbbb

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camect/
"""
import voluptuous as vol

from homeassistant.components import camera
from homeassistant.const import (
    ATTR_NAME, CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv, discovery

REQUIREMENTS = ['camect-py==0.1.0']

ATTR_MODE = 'mode'
CONF_CAMERA_IDS = 'camera_ids'
DEFAULT_HOST = 'camect.local'
DEFAULT_PORT = 8443
DEFAULT_USERNAME = 'admin'
DOMAIN = 'camect'
SERVICE_CHANGE_OP_MODE = 'change_op_mode'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CAMERA_IDS, default=[]): vol.All(
            cv.ensure_list_csv, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)

CHANGE_OP_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MODE): cv.string
})


def setup(hass, config):
    """Set up the Camect component."""
    import camect

    # Create camect.Home instance.
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    home = camect.Home(
        '{}:{}'.format(host, port), conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD))
    hass.data[DOMAIN] = home
    discovery.load_platform(
        hass, camera.DOMAIN, DOMAIN, conf.get(CONF_CAMERA_IDS), config)

    # Register event listener.
    def on_camect_event(evt):
        evt_tp = evt['type']
        if evt_tp == ATTR_NAME:
            pass
        elif evt_tp == ATTR_MODE:
            pass
        hass.bus.fire('camect_event', evt)
    home.add_event_listener(lambda evt: hass.bus.fire('camect_event', evt))

    # Register service.
    def handle_change_op_mode_service(call):
        mode = call.data.get(ATTR_MODE).upper()
        if mode == 'HOME' or mode == 'DEFAULT':
            home.set_mode(mode)
        elif mode == 'AWAY':
            home.set_mode('DEFAULT')
    hass.services.register(
        DOMAIN, SERVICE_CHANGE_OP_MODE, handle_change_op_mode_service,
        schema=CHANGE_OP_MODE_SCHEMA)

    return True
