"""
Support for repeating alerts when conditions are met.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alert/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
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

CONF_NOTIFIERS = 'notifiers'
CONF_REPEAT = 'repeat'
CONF_SKIP_FIRST = 'skip_first'

DOMAIN = 'alert'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

ALERT_SCHEMA = vol.Schema({
    # pylint: disable=no-value-for-parameter
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ENTITY_ID): cv.string,
    vol.Optional(CONF_STATE): cv.string,
    vol.Required(CONF_REPEAT): cv.positive_int,
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
    """Return if the alert is acknowledged."""
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id):
    """Acknowledge the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@callback
def async_turn_on(hass, entity_id):
    """Async acknowledge the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


def turn_off(hass, entity_id):
    """Reset alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@callback
def async_turn_off(hass, entity_id):
    """Async reset the alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))


def toggle(hass, entity_id):
    """Toggle acknowledgement of alert."""
    data = {ATTR_ENTITY_ID: entity_id}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


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
        entity = Alert(hass, alert[CONF_NAME], alert[CONF_ENTITY_ID],
                       alert.get(CONF_STATE, STATE_ON), alert[CONF_REPEAT],
                       alert.get(CONF_SKIP_FIRST, False),
                       alert[CONF_NOTIFIERS])
        all_alerts[entity.entity_id] = entity

    descriptions = {}

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_alert_service,
        descriptions.get(SERVICE_TURN_OFF), schema=ALERT_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_alert_service,
        descriptions.get(SERVICE_TURN_ON), schema=ALERT_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_alert_service,
        descriptions.get(SERVICE_TOGGLE), schema=ALERT_SERVICE_SCHEMA)

    return True


class Alert(ToggleEntity):
    """Representation of an alert."""

    def __init__(self, hass, name, entity, state, repeat, skip_first,
                 notifiers):
        """Initialize the alert."""
        self.hass = hass
        self._name = name
        self._alert_state = state
        self._repeat = timedelta(minutes=repeat)
        self._skip_first = skip_first
        self._notifiers = notifiers
        self._firing = False
        self._ack = False
        self._cancel = None
        self.entity_id = ENTITY_ID_FORMAT.format(slugify(name))

        event.async_track_state_change(hass, entity,
                                       self.watched_entity_change)

    @property
    def name(self):
        """Return the name of the URL."""
        return self._name

    @property
    def state(self):
        """Return the URL."""
        if self._firing:
            if self._ack:
                return STATE_OFF
            return STATE_ON
        return STATE_IDLE

    @property
    def hidden(self):
        """Hide the alert when it is not firing."""
        return not self._firing

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

        if not self._skip_first:
            self._notify()
        else:
            self._schedule_notify()

        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def end_alerting(self):
        """End the alert procedures."""
        _LOGGER.info('Ending Alert: %s', self._name)
        self._cancel()
        self._ack = False
        self._firing = False
        yield from self.async_update_ha_state()

    @callback
    def _schedule_notify(self):
        """Schedule a notification."""
        self._cancel = \
            event.async_track_time_interval(self.hass, self._notify,
                                            self._repeat)

    def _notify(self, *args):
        """Send the alert notification."""
        if not self._firing:
            return

        if not self._ack:
            _LOGGER.info('Alerting: %s', self._name)
            for target in self._notifiers:
                self.hass.services.call(
                    'notify', target, {'message': self._name})
        self._schedule_notify()

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
