"""
Support for repeating alerts when conditions are met.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alert/
"""
import asyncio
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (CONF_ENTITIES, CONF_ENTITY_ID, STATE_IDLE,
                                 CONF_NAME, CONF_STATE, STATE_ON, STATE_OFF,
                                 SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                 SERVICE_TOGGLE, ATTR_ENTITY_ID)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers import service, event
from homeassistant.util import slugify
from homeassistant.util.async import run_callback_threadsafe
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'alert'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_BACKOFF = 'backoff'
CONF_CAN_ACK = 'can_acknowledge'
CONF_NOTIFIERS = 'notifiers'
CONF_REPEAT = 'repeat'
CONF_SKIP_FIRST = 'skip_first'

DEFAULT_BACKOFF = 1
DEFAULT_CAN_ACK = True
DEFAULT_SKIP_FIRST = False
DEFAULT_STATE = STATE_ON

MIN_DELAY = timedelta(minutes=1)
MAX_DELAY = timedelta(days=1)

ALERT_SCHEMA = vol.Schema({
    # pylint: disable=no-value-for-parameter
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ENTITY_ID): cv.string,
    vol.Optional(CONF_STATE): cv.string,
    vol.Required(CONF_REPEAT): cv.positive_int,
    vol.Optional(CONF_BACKOFF): vol.Any(int, float),
    vol.Optional(CONF_CAN_ACK): cv.boolean,
    vol.Optional(CONF_SKIP_FIRST): cv.boolean,
    vol.Required(CONF_NOTIFIERS): cv.ensure_list})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ENTITIES): [ALERT_SCHEMA],
    }),
}, extra=vol.ALLOW_EXTRA)


ALERT_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})


def is_on(hass, entity_id):
    """Return if the alert is firing and not acknowledged."""
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id):
    """Reset the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@callback
def async_turn_on(hass, entity_id):
    """Async reset the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


def turn_off(hass, entity_id):
    """Acknowledge alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@callback
def async_turn_off(hass, entity_id):
    """Async acknowledge the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))


def toggle(hass, entity_id):
    """Toggle acknowledgement of alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


def setup(hass, config):
    """Setup alert component."""
    run_callback_threadsafe(hass.loop, async_setup(hass, config))


@asyncio.coroutine
def async_setup(hass, config):
    """Setup alert component."""
    alerts = config.get(DOMAIN)
    all_alerts = {}

    @asyncio.coroutine
    def async_handle_alert_service(service_call):
        """Handle calls to alert services."""
        alert_ids = service.extract_entity_ids(hass, service_call)

        for alert_id in alert_ids:
            alert = all_alerts[alert_id]
            if service_call.service == SERVICE_TURN_ON:
                yield from alert.async_turn_on()
            elif service_call.service == SERVICE_TOGGLE:
                yield from alert.async_toggle()
            else:
                yield from alert.async_turn_off()

    for alert in alerts.get(CONF_ENTITIES):
        entity = Alert(hass, alert[CONF_NAME],
                       alert[CONF_ENTITY_ID],
                       alert.get(CONF_STATE, DEFAULT_STATE),
                       alert[CONF_REPEAT],
                       alert.get(CONF_SKIP_FIRST, DEFAULT_SKIP_FIRST),
                       alert[CONF_NOTIFIERS],
                       alert.get(CONF_CAN_ACK, DEFAULT_CAN_ACK),
                       alert.get(CONF_BACKOFF, DEFAULT_BACKOFF))
        all_alerts[entity.entity_id] = entity

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))
    descriptions = descriptions.get(DOMAIN, {})

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_alert_service,
        descriptions.get(SERVICE_TURN_OFF), schema=ALERT_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_alert_service,
        descriptions.get(SERVICE_TURN_ON), schema=ALERT_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_alert_service,
        descriptions.get(SERVICE_TOGGLE), schema=ALERT_SERVICE_SCHEMA)

    for alert in all_alerts.values():
        yield from alert.async_update_ha_state()

    return True


class Alert(ToggleEntity):
    """Representation of an alert."""

    def __init__(self, hass, name, entity, state, repeat, skip_first,
                 notifiers, can_ack, backoff):
        """Initialize the alert."""
        self.hass = hass
        self._name = name
        self._alert_state = state
        self._delay = timedelta(minutes=repeat)
        self._skip_first = skip_first
        self._notifiers = notifiers
        self._can_ack = can_ack
        self._backoff = backoff

        self._next_delay = None
        self._firing = False
        self._ack = False
        self._cancel = None
        self.entity_id = ENTITY_ID_FORMAT.format(slugify(name))

        event.async_track_state_change(hass, entity,
                                       self.watched_entity_change)

    @property
    def name(self):
        """Return the name of the alert."""
        return self._name

    @property
    def state(self):
        """Return the alert status."""
        if self._firing:
            if self._ack:
                return STATE_OFF
            return STATE_ON
        return STATE_IDLE

    @property
    def hidden(self):
        """Hide the alert when it is not firing."""
        return not self._can_ack or not self._firing

    @asyncio.coroutine
    def watched_entity_change(self, entity, from_state, to_state):
        """Determine if the alert should start or stop."""
        _LOGGER.debug('Watched entity (%s) has changed.', entity)
        if to_state.state == self._alert_state and not self._firing:
            return self.begin_alerting()
        if to_state.state != self._alert_state and self._firing:
            return self.end_alerting()

    @asyncio.coroutine
    def begin_alerting(self):
        """Begin the alert procedures."""
        _LOGGER.info('Begining Alert: %s', self._name)
        self._ack = False
        self._firing = True
        self._next_delay = self._delay

        if not self._skip_first:
            yield from self._notify()
        else:
            yield from self._schedule_notify()

        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def end_alerting(self):
        """End the alert procedures."""
        _LOGGER.info('Ending Alert: %s', self._name)
        self._cancel()
        self._ack = False
        self._firing = False
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def _schedule_notify(self):
        """Schedule a notification."""
        self._cancel = \
            event.async_track_time_interval(self.hass, self._notify,
                                            self._next_delay)
        self._next_delay = \
            min(max(self._next_delay * self._backoff, MIN_DELAY), MAX_DELAY)

    @asyncio.coroutine
    def _notify(self, *args):
        """Send the alert notification."""
        if not self._firing:
            return

        if not self._ack:
            _LOGGER.info('Alerting: %s', self._name)
            for target in self._notifiers:
                yield from self.hass.services.async_call(
                    'notify', target, {'message': self._name})
        yield from self._schedule_notify()

    def turn_on(self):
        """Unacknowledge alert."""
        run_callback_threadsafe(self.hass.loop, self.async_turn_on)

    @asyncio.coroutine
    def async_turn_on(self):
        """Async Unacknowledge alert."""
        _LOGGER.debug('Reset Alert: %s', self._name)
        self._ack = False
        yield from self.async_update_ha_state()

    def turn_off(self):
        """Acknowledge alert."""
        run_callback_threadsafe(self.hass.loop, self.async_turn_off)

    @asyncio.coroutine
    def async_turn_off(self):
        """Async Acknowledge alert."""
        _LOGGER.debug('Acknowledged Alert: %s', self._name)
        self._ack = True
        yield from self.async_update_ha_state()

    def toggle(self):
        """Toggle alert."""
        run_callback_threadsafe(self.hass.loop, self.async_toggle)

    @asyncio.coroutine
    def async_toggle(self):
        """Async toggle alert."""
        if self._ack:
            return self.async_turn_on()
        return self.async_turn_off()
