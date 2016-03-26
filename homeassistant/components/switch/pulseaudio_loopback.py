"""
Switch logic for loading/unloading pulseaudio loopback modules.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pulseaudio_loopback/
"""
import logging
import re
import socket

from homeassistant.components.switch import SwitchDevice
from homeassistant.util import convert

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "paloopback"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4712
DEFAULT_BUFFER_SIZE = 1024
DEFAULT_TCP_TIMEOUT = 3
LOAD_CMD = "load-module module-loopback sink={0} source={1}"
UNLOAD_CMD = "unload-module {0}"
MOD_REGEX = r"index: ([0-9]+)\s+name: <module-loopback>" \
            r"\s+argument: <sink={0} source={1}>"


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Read in all of our configuration, and initialize the loopback switch."""
    if config.get('sink_name') is None:
        _LOGGER.error("Missing required variable: sink_name")
        return False

    if config.get('source_name') is None:
        _LOGGER.error("Missing required variable: source_name")
        return False

    add_devices_callback([PALoopbackSwitch(
        hass,
        convert(config.get('name'), str, DEFAULT_NAME),
        convert(config.get('host'), str, DEFAULT_HOST),
        convert(config.get('port'), int, DEFAULT_PORT),
        convert(config.get('buffer_size'), int, DEFAULT_BUFFER_SIZE),
        convert(config.get('tcp_timeout'), int, DEFAULT_TCP_TIMEOUT),
        config.get('sink_name'),
        config.get('source_name')
        )])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class PALoopbackSwitch(SwitchDevice):
    """Represents the presence or absence of a pa loopback module."""

    def __init__(self, hass, name, pa_host, pa_port, buff_sz,
                 tcp_timeout, sink_name, source_name):
        """Initialize the switch."""
        self._module_idx = -1
        self._hass = hass
        self._name = name
        self._pa_host = pa_host
        self._pa_port = int(pa_port)
        self._sink_name = sink_name
        self._source_name = source_name
        self._buffer_size = int(buff_sz)
        self._tcp_timeout = int(tcp_timeout)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Tell the core logic if device is on."""
        return self._module_idx > 0

    def _send_command(self, cmd, response_expected):
        """Send a command to the pa server using a socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._tcp_timeout)
        try:
            sock.connect((self._pa_host, self._pa_port))
            _LOGGER.info("Calling pulseaudio:" + cmd)
            sock.send((cmd + "\n").encode("utf-8"))
            if response_expected:
                return_data = self._get_full_response(sock)
                _LOGGER.debug("Data received from pulseaudio: " + return_data)
            else:
                return_data = ""
        finally:
            sock.close()
        return return_data

    def _get_full_response(self, sock):
        """Helper method to get the full response back from pulseaudio."""
        result = ""
        rcv_buffer = sock.recv(self._buffer_size)
        result += rcv_buffer.decode("utf-8")

        while len(rcv_buffer) == self._buffer_size:
            rcv_buffer = sock.recv(self._buffer_size)
            result += rcv_buffer.decode("utf-8")

        return result

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command(str.format(LOAD_CMD,
                                      self._sink_name,
                                      self._source_name),
                           False)
        self.update()
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command(str.format(UNLOAD_CMD, self._module_idx), False)
        self.update()
        self.update_ha_state()

    def update(self):
        """Refresh state in case an alternate process modified this data."""
        return_data = self._send_command("list-modules", True)
        result = re.search(str.format(MOD_REGEX,
                                      re.escape(self._sink_name),
                                      re.escape(self._source_name)),
                           return_data)
        if result and result.group(1).isdigit():
            self._module_idx = int(result.group(1))
        else:
            self._module_idx = -1
