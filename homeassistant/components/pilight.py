"""
Component to create an interface to a Pilight daemon (https://pilight.org/).

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/pilight/
"""
import logging
import socket

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_PORT,
    CONF_WHITELIST)

REQUIREMENTS = ['pilight==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_PROTOCOL = 'protocol'

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000
DOMAIN = 'pilight'

EVENT = 'pilight_received'

# The pilight code schema depends on the protocol
# Thus only require to have the protocol information
# Ensure that protocol is in a list otherwise segfault in pilight-daemon
# https://github.com/pilight/pilight/issues/296
RF_CODE_SCHEMA = vol.Schema({vol.Required(ATTR_PROTOCOL):
                             vol.All(cv.ensure_list, [cv.string])},
                            extra=vol.ALLOW_EXTRA)
SERVICE_NAME = 'send'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_WHITELIST, default={}): {cv.string: [cv.string]}
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the pilight component."""
    from pilight import pilight

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]

    try:
        pilight_client = pilight.Client(host=host, port=port)
    except (socket.error, socket.timeout) as err:
        _LOGGER.error("Unable to connect to %s on port %s: %s",
                      host, port, err)
        return False

    # Start / stop pilight-daemon connection with HA start/stop
    def start_pilight_client(_):
        """Called once when home assistant starts."""
        pilight_client.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_pilight_client)

    def stop_pilight_client(_):
        """Called once when home assistant stops."""
        pilight_client.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_pilight_client)

    def send_code(call):
        """Send RF code to the pilight-daemon."""
        # Change type to dict from mappingproxy
        # since data has to be JSON serializable
        message_data = dict(call.data)

        try:
            pilight_client.send_code(message_data)
        except IOError:
            _LOGGER.error('Pilight send failed for %s', str(message_data))

    hass.services.register(DOMAIN, SERVICE_NAME,
                           send_code, schema=RF_CODE_SCHEMA)

    # Publish received codes on the HA event bus
    # A whitelist of codes to be published in the event bus
    whitelist = config[DOMAIN].get(CONF_WHITELIST)

    def handle_received_code(data):
        """Called when RF codes are received."""
        # Unravel dict of dicts to make event_data cut in automation rule
        # possible
        data = dict(
            {'protocol': data['protocol'],
             'uuid': data['uuid']},
            **data['message'])

        # No whitelist defined, put data on event bus
        if not whitelist:
            hass.bus.fire(EVENT, data)
        # Check if data matches the defined whitelist
        elif all(data[key] in whitelist[key] for key in whitelist):
            hass.bus.fire(EVENT, data)

    pilight_client.set_callback(handle_received_code)

    return True
