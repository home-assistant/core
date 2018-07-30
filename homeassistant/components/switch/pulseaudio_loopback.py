"""
Switch logic for loading/unloading pulseaudio loopback modules.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pulseaudio_loopback/
"""
import logging
import re
import socket
from datetime import timedelta

import voluptuous as vol

from homeassistant import util
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_PULSEAUDIO_SERVERS = {}

CONF_BUFFER_SIZE = 'buffer_size'
CONF_SINK_NAME = 'sink_name'
CONF_SOURCE_NAME = 'source_name'
CONF_TCP_TIMEOUT = 'tcp_timeout'

DEFAULT_BUFFER_SIZE = 1024
DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'paloopback'
DEFAULT_PORT = 4712
DEFAULT_TCP_TIMEOUT = 3

IGNORED_SWITCH_WARN = "Switch is already in the desired state. Ignoring."

LOAD_CMD = "load-module module-loopback sink={0} source={1}"

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MOD_REGEX = r"index: ([0-9]+)\s+name: <module-loopback>" \
            r"\s+argument: (?=<.*sink={0}.*>)(?=<.*source={1}.*>)"

UNLOAD_CMD = "unload-module {0}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SINK_NAME): cv.string,
    vol.Required(CONF_SOURCE_NAME): cv.string,
    vol.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE):
        cv.positive_int,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TCP_TIMEOUT, default=DEFAULT_TCP_TIMEOUT):
        cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Read in all of our configuration, and initialize the loopback switch."""
    name = config.get(CONF_NAME)
    sink_name = config.get(CONF_SINK_NAME)
    source_name = config.get(CONF_SOURCE_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    buffer_size = config.get(CONF_BUFFER_SIZE)
    tcp_timeout = config.get(CONF_TCP_TIMEOUT)

    server_id = str.format("{0}:{1}", host, port)

    if server_id in _PULSEAUDIO_SERVERS:
        server = _PULSEAUDIO_SERVERS[server_id]
    else:
        server = PAServer(host, port, buffer_size, tcp_timeout)
        _PULSEAUDIO_SERVERS[server_id] = server

    add_devices([PALoopbackSwitch(hass, name, server, sink_name, source_name)])


class PAServer():
    """Representation of a Pulseaudio server."""

    _current_module_state = ""

    def __init__(self, host, port, buff_sz, tcp_timeout):
        """Initialize PulseAudio server."""
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
            _LOGGER.info("Calling pulseaudio: %s", cmd)
            sock.send((cmd + "\n").encode("utf-8"))
            if response_expected:
                return_data = self._get_full_response(sock)
                _LOGGER.debug("Data received from pulseaudio: %s", return_data)
            else:
                return_data = ""
        finally:
            sock.close()
        return return_data

    def _get_full_response(self, sock):
        """Get the full response back from pulseaudio."""
        result = ""
        rcv_buffer = sock.recv(self._buffer_size)
        result += rcv_buffer.decode('utf-8')

        while len(rcv_buffer) == self._buffer_size:
            rcv_buffer = sock.recv(self._buffer_size)
            result += rcv_buffer.decode('utf-8')

        return result

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_module_state(self):
        """Refresh state in case an alternate process modified this data."""
        self._current_module_state = self._send_command("list-modules", True)

    def turn_on(self, sink_name, source_name):
        """Send a command to pulseaudio to turn on the loopback."""
        self._send_command(str.format(LOAD_CMD, sink_name, source_name), False)

    def turn_off(self, module_idx):
        """Send a command to pulseaudio to turn off the loopback."""
        self._send_command(str.format(UNLOAD_CMD, module_idx), False)

    def get_module_idx(self, sink_name, source_name):
        """For a sink/source, return its module id in our cache, if found."""
        result = re.search(str.format(MOD_REGEX, re.escape(sink_name),
                                      re.escape(source_name)),
                           self._current_module_state)
        if result and result.group(1).isdigit():
            return int(result.group(1))
        return -1


class PALoopbackSwitch(SwitchDevice):
    """Representation the presence or absence of a PA loopback module."""

    def __init__(self, hass, name, pa_server, sink_name, source_name):
        """Initialize the Pulseaudio switch."""
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
        """Return true if device is on."""
        return self._module_idx > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if not self.is_on:
            self._pa_svr.turn_on(self._sink_name, self._source_name)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(
                self._sink_name, self._source_name)
            self.schedule_update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.is_on:
            self._pa_svr.turn_off(self._module_idx)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(
                self._sink_name, self._source_name)
            self.schedule_update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def update(self):
        """Refresh state in case an alternate process modified this data."""
        self._pa_svr.update_module_state()
        self._module_idx = self._pa_svr.get_module_idx(
            self._sink_name, self._source_name)
