"""
Switch logic for loading/unloading pulseaudio loopback modules.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pulseaudio_loopback/
"""
import logging
import re
import socket
from datetime import timedelta

import homeassistant.util as util
from homeassistant.components.switch import SwitchDevice
from homeassistant.util import convert

_LOGGER = logging.getLogger(__name__)
_PULSEAUDIO_SERVERS = {}

DEFAULT_NAME = "paloopback"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4712
DEFAULT_BUFFER_SIZE = 1024
DEFAULT_TCP_TIMEOUT = 3
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

LOAD_CMD = "load-module module-loopback sink={0} source={1}"
UNLOAD_CMD = "unload-module {0}"
MOD_REGEX = r"index: ([0-9]+)\s+name: <module-loopback>" \
            r"\s+argument: (?=<.*sink={0}.*>)(?=<.*source={1}.*>)"

IGNORED_SWITCH_WARN = "Switch is already in the desired state. Ignoring."


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Read in all of our configuration, and initialize the loopback switch."""
    if config.get('sink_name') is None:
        _LOGGER.error("Missing required variable: sink_name")
        return False

    if config.get('source_name') is None:
        _LOGGER.error("Missing required variable: source_name")
        return False

    name = convert(config.get('name'), str, DEFAULT_NAME)
    sink_name = config.get('sink_name')
    source_name = config.get('source_name')
    host = convert(config.get('host'), str, DEFAULT_HOST)
    port = convert(config.get('port'), int, DEFAULT_PORT)
    buffer_size = convert(config.get('buffer_size'), int, DEFAULT_BUFFER_SIZE)
    tcp_timeout = convert(config.get('tcp_timeout'), int, DEFAULT_TCP_TIMEOUT)

    server_id = str.format("{0}:{1}", host, port)

    if server_id in _PULSEAUDIO_SERVERS:
        server = _PULSEAUDIO_SERVERS[server_id]

    else:
        server = PAServer(host, port, buffer_size, tcp_timeout)

        _PULSEAUDIO_SERVERS[server_id] = server

    add_devices_callback([PALoopbackSwitch(
        hass,
        name,
        server,
        sink_name,
        source_name
        )])


class PAServer():
    """Represents a pulseaudio server."""

    _current_module_state = ""

    def __init__(self, host, port, buff_sz, tcp_timeout):
        """Simple constructor for reading in our configuration."""
        self._pa_host = host
        self._pa_port = int(port)
        self._buffer_size = int(buff_sz)
        self._tcp_timeout = int(tcp_timeout)

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

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_module_state(self):
        """Refresh state in case an alternate process modified this data."""
        self._current_module_state = self._send_command("list-modules", True)

    def turn_on(self, sink_name, source_name):
        """Send a command to pulseaudio to turn on the loopback."""
        self._send_command(str.format(LOAD_CMD,
                                      sink_name,
                                      source_name),
                           False)

    def turn_off(self, module_idx):
        """Send a command to pulseaudio to turn off the loopback."""
        self._send_command(str.format(UNLOAD_CMD, module_idx), False)

    def get_module_idx(self, sink_name, source_name):
        """For a sink/source, return it's module id in our cache, if found."""
        result = re.search(str.format(MOD_REGEX,
                                      re.escape(sink_name),
                                      re.escape(source_name)),
                           self._current_module_state)
        if result and result.group(1).isdigit():
            return int(result.group(1))
        else:
            return -1


# pylint: disable=too-many-arguments
class PALoopbackSwitch(SwitchDevice):
    """Represents the presence or absence of a pa loopback module."""

    def __init__(self, hass, name, pa_server,
                 sink_name, source_name):
        """Initialize the switch."""
        self._module_idx = -1
        self._hass = hass
        self._name = name
        self._sink_name = sink_name
        self._source_name = source_name
        self._pa_svr = pa_server

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Tell the core logic if device is on."""
        return self._module_idx > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if not self.is_on:
            self._pa_svr.turn_on(self._sink_name, self._source_name)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(self._sink_name,
                                                           self._source_name)
            self.update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.is_on:
            self._pa_svr.turn_off(self._module_idx)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(self._sink_name,
                                                           self._source_name)
            self.update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def update(self):
        """Refresh state in case an alternate process modified this data."""
        self._pa_svr.update_module_state()
        self._module_idx = self._pa_svr.get_module_idx(self._sink_name,
                                                       self._source_name)
