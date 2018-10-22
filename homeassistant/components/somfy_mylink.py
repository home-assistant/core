"""
Platform for the Somfy MyLink device supporting the Synergy JsonRPC API.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/somfy_mylink/
"""
import json
import logging
import socket
from random import randint
import voluptuous as vol
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

_LOGGER = logging.getLogger(__name__)
CONF_COVER_OPTIONS = 'cover_options'
DATA_SOMFY_MYLINK = 'somfy_mylink_data'
DOMAIN = 'somfy_mylink'
SOMFY_MYLINK_COMPONENTS = [
    'cover', 'scene'
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=44100): cv.port,
        vol.Optional(CONF_COVER_OPTIONS): cv.ensure_list
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Demo covers."""
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    system_id = config[DOMAIN][CONF_PASSWORD]
    try:
        somfy_mylink = SomfyMyLink(host, port, system_id)
    except TimeoutError:
        _LOGGER.error("Unable to connect to the Somfy MyLink device, "
                      "please check your settings")
        return False
    hass.data[DATA_SOMFY_MYLINK] = somfy_mylink
    for component in SOMFY_MYLINK_COMPONENTS:
        load_platform(hass, component, DOMAIN, config[DOMAIN])
    return True


class SomfyMyLink:
    """API Wrapper for the Somfy MyLink device."""

    def __init__(self, host, port, system_id):
        """Create the object with required parameters."""
        self.host = host
        self.port = port
        self.system_id = system_id

    def scene_list(self):
        """List all somfy scenes."""
        message = self.build_message("mylink.scene.list")
        return self.send_message(message)

    def scene_run(self, scene_id):
        """Run specified Somfy scene."""
        message = self.build_message(
            "mylink.scene.run", dict(sceneID=scene_id))
        return self.send_message(message)

    def status_info(self, target_id="*.*"):
        """Retrieve info on all Somfy devices."""
        message = self.build_message(
            "mylink.status.info", dict(targetID=target_id))
        return self.send_message(message)

    def status_ping(self, target_id="*.*"):
        """Send a Ping message to all Somfy devices."""
        message = self.build_message(
            "mylink.status.ping", dict(targetID=target_id))
        return self.send_message(message)

    def move_up(self, target_id):
        """Format a Move up message and send it."""
        message = self.build_message(
            "mylink.move.up", dict(targetID=target_id))
        return self.send_message(message)

    def move_down(self, target_id):
        """Format a Move Down message and send it."""
        message = self.build_message(
            "mylink.move.down", dict(targetID=target_id))
        return self.send_message(message)

    def move_stop(self, target_id):
        """Format a Stop message and send it."""
        message = self.build_message(
            "mylink.move.stop", dict(targetID=target_id))
        return self.send_message(message)

    def build_message(self, method=None, params=None):
        """Format a JSON API message."""
        # Set "empty" values if none passed in to funciton
        method = method if method else str()
        params = params if params else dict()
        message = dict(method=method, params=params, id=randint(0, 100))
        message['params']['auth'] = self.system_id
        return message

    def send_message(self, message, retry_count=3):
        """Send a message to MyLink using JsonRPC via Socket."""
        message_as_bytes = str.encode(json.dumps(message))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            _LOGGER.info(message)
            sock.connect((self.host, self.port))
            sock.sendall(message_as_bytes)
            sock.shutdown(socket.SHUT_WR)
        except OSError as ex:
            _LOGGER.info("Failed to send msg: %s", ex)
            raise TimeoutError("Unable to open socket") from ex
        try:
            data_bytes = sock.recv(1024)
            data_string = data_bytes.decode("utf-8")
            data_dict = json.loads(data_string)
            _LOGGER.debug(data_dict)
            return data_dict
        except OSError as ex:
            if retry_count > 0:
                _LOGGER.info("Retrying with incremented id,"
                             "retries left: %s", retry_count)
                message['id'] += 10
                return self.send_message(message, retry_count - 1)
            _LOGGER.info("Got error when receiving: %s", ex)
            raise TimeoutError("No response from the device") from ex
