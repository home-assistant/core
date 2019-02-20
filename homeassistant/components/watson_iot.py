"""
A component which allows you to send data to the IBM Watson IoT Platform.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/watson_iot/
"""
import logging
import queue
import threading
import time

import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_ID, CONF_INCLUDE,
    CONF_TOKEN, CONF_TYPE, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['ibmiotf==0.3.4']

_LOGGER = logging.getLogger(__name__)

CONF_ORG = 'organization'

DOMAIN = 'watson_iot'

MAX_TRIES = 3

RETRY_DELAY = 20

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(vol.Schema({
        vol.Required(CONF_ORG): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_EXCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
        vol.Optional(CONF_INCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
    })),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Watson IoT Platform component."""
    from ibmiotf import gateway

    conf = config[DOMAIN]

    include = conf[CONF_INCLUDE]
    exclude = conf[CONF_EXCLUDE]
    whitelist_e = set(include[CONF_ENTITIES])
    whitelist_d = set(include[CONF_DOMAINS])
    blacklist_e = set(exclude[CONF_ENTITIES])
    blacklist_d = set(exclude[CONF_DOMAINS])

    client_args = {
        'org': conf[CONF_ORG],
        'type': conf[CONF_TYPE],
        'id': conf[CONF_ID],
        'auth-method': 'token',
        'auth-token': conf[CONF_TOKEN],
    }
    watson_gateway = gateway.Client(client_args)

    def event_to_json(event):
        """Add an event to the outgoing list."""
        state = event.data.get('new_state')
        if state is None or state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE) or \
                state.entity_id in blacklist_e or state.domain in blacklist_d:
            return

        if (whitelist_e and state.entity_id not in whitelist_e) or \
                (whitelist_d and state.domain not in whitelist_d):
            return

        try:
            _state_as_value = float(state.state)
        except ValueError:
            _state_as_value = None

        if _state_as_value is None:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
            except ValueError:
                _state_as_value = None

        out_event = {
            'tags': {
                'domain': state.domain,
                'entity_id': state.object_id,
            },
            'time': event.time_fired.isoformat(),
            'fields': {
                'state': state.state,
            }
        }
        if _state_as_value is not None:
            out_event['fields']['state_value'] = _state_as_value

        for key, value in state.attributes.items():
            if key != 'unit_of_measurement':
                # If the key is already in fields
                if key in out_event['fields']:
                    key = '{}_'.format(key)
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string
                try:
                    out_event['fields'][key] = float(value)
                except (ValueError, TypeError):
                    out_event['fields'][key] = str(value)

        return out_event

    instance = hass.data[DOMAIN] = WatsonIOTThread(
        hass, watson_gateway, event_to_json)
    instance.start()

    def shutdown(event):
        """Shut down the thread."""
        instance.queue.put(None)
        instance.join()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class WatsonIOTThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, gateway, event_to_json):
        """Initialize the listener."""
        threading.Thread.__init__(self, name='WatsonIOT')
        self.queue = queue.Queue()
        self.gateway = gateway
        self.gateway.connect()
        self.event_to_json = event_to_json
        self.write_errors = 0
        self.shutdown = False
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for Watson IoT."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    def get_events_json(self):
        """Return an event formatted for writing."""
        events = []

        try:
            item = self.queue.get()

            if item is None:
                self.shutdown = True
            else:
                event_json = self.event_to_json(item[1])
                if event_json:
                    events.append(event_json)

        except queue.Empty:
            pass

        return events

    def write_to_watson(self, events):
        """Write preprocessed events to watson."""
        import ibmiotf

        for event in events:
            for retry in range(MAX_TRIES + 1):
                try:
                    for field in event['fields']:
                        value = event['fields'][field]
                        device_success = self.gateway.publishDeviceEvent(
                            event['tags']['domain'],
                            event['tags']['entity_id'],
                            field, 'json', value)
                    if not device_success:
                        _LOGGER.error(
                            "Failed to publish message to Watson IoT")
                        continue
                    break
                except (ibmiotf.MissingMessageEncoderException, IOError):
                    if retry < MAX_TRIES:
                        time.sleep(RETRY_DELAY)
                    else:
                        _LOGGER.exception(
                            "Failed to publish message to Watson IoT")

    def run(self):
        """Process incoming events."""
        while not self.shutdown:
            event = self.get_events_json()
            if event:
                self.write_to_watson(event)
            self.queue.task_done()

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()
