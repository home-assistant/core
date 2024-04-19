"""Support for sending data to a Graphite installation."""

from contextlib import suppress
import logging
import queue
import socket
import threading
import time

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PREFIX,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import state
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PROTOCOL_TCP = "tcp"
PROTOCOL_UDP = "udp"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 2003
DEFAULT_PROTOCOL = PROTOCOL_TCP
DEFAULT_PREFIX = "ha"
DOMAIN = "graphite"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.Any(
                    PROTOCOL_TCP, PROTOCOL_UDP
                ),
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Graphite feeder."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    prefix = conf.get(CONF_PREFIX)
    port = conf.get(CONF_PORT)
    protocol = conf.get(CONF_PROTOCOL)

    if protocol == PROTOCOL_TCP:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            sock.shutdown(2)
            _LOGGER.debug("Connection to Graphite possible")
        except OSError:
            _LOGGER.error("Not able to connect to Graphite")
            return False
    else:
        _LOGGER.debug("No connection check for UDP possible")

    hass.data[DOMAIN] = GraphiteFeeder(hass, host, port, protocol, prefix)
    return True


class GraphiteFeeder(threading.Thread):
    """Feed data to Graphite."""

    def __init__(self, hass, host, port, protocol, prefix):
        """Initialize the feeder."""
        super().__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        self._protocol = protocol
        # rstrip any trailing dots in case they think they need it
        self._prefix = prefix.rstrip(".")
        self._queue = queue.Queue()
        self._quit_object = object()
        self._unsub_state_changed = None

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.start_listen)
        _LOGGER.debug("Graphite feeding to %s:%i initialized", self._host, self._port)

    def start_listen(self, event):
        """Start event-processing thread."""
        _LOGGER.debug("Event processing thread started")
        self._hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        self._unsub_state_changed = self._hass.bus.listen(
            EVENT_STATE_CHANGED, self.event_listener
        )
        self.start()

    def shutdown(self, event):
        """Signal shutdown of processing event."""
        _LOGGER.debug("Event processing signaled exit")
        self._unsub_state_changed()
        self._unsub_state_changed = None
        self._queue.put(self._quit_object)
        self._queue.join()

    def event_listener(self, event):
        """Queue an event for processing."""
        if self._unsub_state_changed is not None:
            _LOGGER.debug("Received event")
            self._queue.put(event)
        else:
            _LOGGER.error("Graphite feeder thread has died, not queuing event")

    def _send_to_graphite(self, data):
        """Send data to Graphite."""
        if self._protocol == PROTOCOL_TCP:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self._host, self._port))
            sock.sendall(data.encode("ascii"))
            sock.send(b"\n")
            sock.close()
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data.encode("ascii") + b"\n", (self._host, self._port))

    def _report_attributes(self, entity_id, new_state):
        """Report the attributes."""
        now = time.time()
        things = dict(new_state.attributes)
        with suppress(ValueError):
            things["state"] = state.state_as_number(new_state)
        lines = [
            "%s.%s.%s %f %i"
            % (self._prefix, entity_id, key.replace(" ", "_"), value, now)
            for key, value in things.items()
            if isinstance(value, (float, int))
        ]
        if not lines:
            return
        _LOGGER.debug("Sending to graphite: %s", lines)
        try:
            self._send_to_graphite("\n".join(lines))
        except socket.gaierror:
            _LOGGER.error("Unable to connect to host %s", self._host)
        except OSError:
            _LOGGER.exception("Failed to send data to graphite")

    def run(self):
        """Run the process to export the data."""
        while True:
            if (event := self._queue.get()) == self._quit_object:
                _LOGGER.debug("Event processing thread stopped")
                self._queue.task_done()
                return
            if event.event_type == EVENT_STATE_CHANGED:
                if not event.data.get("new_state"):
                    _LOGGER.debug(
                        "Skipping %s without new_state for %s",
                        event.event_type,
                        event.data["entity_id"],
                    )
                    self._queue.task_done()
                    continue

                _LOGGER.debug(
                    "Processing STATE_CHANGED event for %s", event.data["entity_id"]
                )
                try:
                    self._report_attributes(
                        event.data["entity_id"], event.data["new_state"]
                    )
                except Exception:  # pylint: disable=broad-except
                    # Catch this so we can avoid the thread dying and
                    # make it visible.
                    _LOGGER.exception("Failed to process STATE_CHANGED event")
            else:
                _LOGGER.warning("Processing unexpected event type %s", event.event_type)

            self._queue.task_done()
