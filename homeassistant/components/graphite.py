"""
Component that sends data to aGraphite installation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/graphite/
"""
import logging
import queue
import socket
import threading
import time

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED)
from homeassistant.helpers import state

DOMAIN = "graphite"
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the Graphite feeder."""
    graphite_config = config.get('graphite', {})
    host = graphite_config.get('host', 'localhost')
    prefix = graphite_config.get('prefix', 'ha')
    try:
        port = int(graphite_config.get('port', 2003))
    except ValueError:
        _LOGGER.error('Invalid port specified')
        return False

    GraphiteFeeder(hass, host, port, prefix)
    return True


class GraphiteFeeder(threading.Thread):
    """Feed data to Graphite."""

    def __init__(self, hass, host, port, prefix):
        """Initialize the feeder."""
        super(GraphiteFeeder, self).__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        # rstrip any trailing dots in case they think they need it
        self._prefix = prefix.rstrip('.')
        self._queue = queue.Queue()
        self._quit_object = object()
        self._we_started = False

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START,
                             self.start_listen)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             self.shutdown)
        hass.bus.listen(EVENT_STATE_CHANGED, self.event_listener)
        _LOGGER.debug('Graphite feeding to %s:%i initialized',
                      self._host, self._port)

    def start_listen(self, event):
        """Start event-processing thread."""
        _LOGGER.debug('Event processing thread started')
        self._we_started = True
        self.start()

    def shutdown(self, event):
        """Signal shutdown of processing event."""
        _LOGGER.debug('Event processing signaled exit')
        self._queue.put(self._quit_object)

    def event_listener(self, event):
        """Queue an event for processing."""
        if self.is_alive() or not self._we_started:
            _LOGGER.debug('Received event')
            self._queue.put(event)
        else:
            _LOGGER.error('Graphite feeder thread has died, not '
                          'queuing event!')

    def _send_to_graphite(self, data):
        """Send data to Graphite."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((self._host, self._port))
        sock.sendall(data.encode('ascii'))
        sock.send('\n'.encode('ascii'))
        sock.close()

    def _report_attributes(self, entity_id, new_state):
        """Report the attributes."""
        now = time.time()
        things = dict(new_state.attributes)
        try:
            things['state'] = state.state_as_number(new_state)
        except ValueError:
            pass
        lines = ['%s.%s.%s %f %i' % (self._prefix,
                                     entity_id, key.replace(' ', '_'),
                                     value, now)
                 for key, value in things.items()
                 if isinstance(value, (float, int))]
        if not lines:
            return
        _LOGGER.debug('Sending to graphite: %s', lines)
        try:
            self._send_to_graphite('\n'.join(lines))
        except socket.gaierror:
            _LOGGER.error('Unable to connect to host %s', self._host)
        except socket.error:
            _LOGGER.exception('Failed to send data to graphite')

    def run(self):
        """Run the process to export the data."""
        while True:
            event = self._queue.get()
            if event == self._quit_object:
                _LOGGER.debug('Event processing thread stopped')
                self._queue.task_done()
                return
            elif (event.event_type == EVENT_STATE_CHANGED and
                  event.data.get('new_state')):
                _LOGGER.debug('Processing STATE_CHANGED event for %s',
                              event.data['entity_id'])
                try:
                    self._report_attributes(event.data['entity_id'],
                                            event.data['new_state'])
                # pylint: disable=broad-except
                except Exception:
                    # Catch this so we can avoid the thread dying and
                    # make it visible.
                    _LOGGER.exception('Failed to process STATE_CHANGED event')
            else:
                _LOGGER.warning('Processing unexpected event type %s',
                                event.event_type)

            self._queue.task_done()
