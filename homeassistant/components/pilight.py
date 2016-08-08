"""
Component to create an interface to a Pilight daemon (https://pilight.org/).

Pilight can be used to send and receive signals from a radio frequency
module (RF receiver).

RF commands received by the daemon are put on the HA event bus.
RF commands can also be send with a pilight.send service call.
"""
# pylint: disable=import-error
import logging
import socket

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import ensure_list
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.const import CONF_HOST, CONF_PORT

REQUIREMENTS = ['pilight==0.0.2']

DOMAIN = "pilight"
EVENT = 'pilight_received'
SERVICE_NAME = 'send'

CONF_WHITELIST = 'whitelist'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST, default='127.0.0.1'): cv.string,
        vol.Required(CONF_PORT, default=5000): int,
        vol.Optional(CONF_WHITELIST): dict
    }),
}, extra=vol.ALLOW_EXTRA)

# The pilight code schema depends on the protocol
# Thus only require to have the protocol information
ATTR_PROTOCOL = 'protocol'
RF_CODE_SCHEMA = vol.Schema({vol.Required(ATTR_PROTOCOL): cv.string},
                            extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup pilight component."""
    from pilight import pilight

    try:
        pilight_client = pilight.Client(host=config[DOMAIN][CONF_HOST],
                                        port=config[DOMAIN][CONF_PORT])
    except (socket.error, socket.timeout) as err:
        _LOGGER.error(
            "Unable to connect to %s on port %s: %s",
            config[CONF_HOST], config[CONF_PORT], err)
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
        message_data = call.data

        # Patch data because of bug:
        # https://github.com/pilight/pilight/issues/296
        # Protocol has to be in a list otherwise segfault in pilight-daemon
        message_data["protocol"] = ensure_list(message_data["protocol"])

        try:
            pilight_client.send_code(message_data)
        except IOError:
            _LOGGER.error('Pilight send failed for %s', str(message_data))

    hass.services.register(DOMAIN, SERVICE_NAME,
                           send_code, schema=RF_CODE_SCHEMA)

    # Publish received codes on the HA event bus
    # A whitelist of codes to be published in the event bus
    whitelist = config[DOMAIN].get('whitelist', False)

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
