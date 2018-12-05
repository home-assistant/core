"""
Support for CM15A/CM19A X10 Controller using mochad daemon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mochad/
"""
import logging
import threading

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_USERNAME,
                                 CONF_PASSWORD)

REQUIREMENTS = ["pymochad_mqtt>=0.8.4"]
REQUIREMENTS = ['pymochad==0.2.0']

_LOGGER = logging.getLogger(__name__)

CONF_COMM_TYPE = 'comm_type'

DOMAIN = 'mochad'
DOMAIN_MQTT = 'mqtt'
CONF_BROKER = 'broker'

REQ_LOCK = threading.Lock()

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default='localhost'): cv.string,
        vol.Optional(CONF_PORT, default=1099): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the mochad component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    conf_mqtt = config[DOMAIN_MQTT]
    broker = conf_mqtt.get(CONF_BROKER)
    mqtt_port = conf_mqtt.get(CONF_PORT)
    username = conf_mqtt.get(CONF_USERNAME)
    password = conf_mqtt.get(CONF_PASSWORD)

    from pymochad import exceptions

    try:
        CONTROLLER = MochadCtrl(hass, host, port, broker, mqtt_port,
                                username, password)
        hass.data[DOMAIN] = CONTROLLER
    except exceptions.ConfigurationError:
        _LOGGER.exception()
        return False

    def stop_mochad(event):
        """Stop the Mochad service."""
        CONTROLLER = hass.data.get(DOMAIN)
        CONTROLLER.disconnect()

    def start_mochad(event):
        """Start the Mochad service."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mochad)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mochad)

    return True


class MochadCtrl:
    """Mochad controller."""

    def __init__(self, hass, host, port, broker, mqtt_port,
                 username, password):
        """Initialize a PyMochad send-receive controller."""
        self._host = host
        self._port = port

        from pymochad_mqtt import controller

        self.ctrl_recv = controller.\
            PyMochadMqtt(mochad_server=self._host, mochad_port=self._port,
                         mqtt_broker=broker, mqtt_port=mqtt_port,
                         mqtt_auth={"username": username, "password":
                                    password})
        self.ctrl_recv.start()
        _LOGGER.debug("""PyMochadMqtt controller created for mochad {}:{} and
                       mqtt {}:{}""".format(
            host, port, broker, mqtt_port))
        if self.ctrl_recv.connect_event.wait():
            self.ctrl_send = self.ctrl_recv.ctrl

    @property
    def host(self):
        """Return the server where mochad is running."""
        return self._host

    @property
    def port(self):
        """Return the port mochad is running on."""
        return self._port

    def disconnect(self):
        """Close the connection to the mochad socket."""
        self.ctrl_recv.disconnect()
