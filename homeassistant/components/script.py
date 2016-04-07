"""
Support for scripts.

Scripts are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/script/
"""
import logging
import threading
from datetime import timedelta
from itertools import islice

import voluptuous as vol

import homeassistant.util.dt as date_util
from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity, split_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.service import (call_from_config,
                                           validate_service_call)
import homeassistant.helpers.config_validation as cv

DOMAIN = "script"
ENTITY_ID_FORMAT = DOMAIN + '.{}'
DEPENDENCIES = ["group"]

STATE_NOT_RUNNING = 'Not Running'

CONF_ALIAS = "alias"
CONF_SERVICE = "service"
CONF_SERVICE_DATA = "data"
CONF_SEQUENCE = "sequence"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_DELAY = "delay"

ATTR_LAST_ACTION = 'last_action'
ATTR_CAN_CANCEL = 'can_cancel'

_LOGGER = logging.getLogger(__name__)

_ALIAS_VALIDATOR = vol.Schema(cv.string)


def _alias_stripper(validator):
    """Strip alias from object for validation."""
    def validate(value):
        """Validate without alias value."""
        value = value.copy()
        alias = value.pop(CONF_ALIAS, None)

        if alias is not None:
            alias = _ALIAS_VALIDATOR(alias)

        value = validator(value)

        if alias is not None:
            value[CONF_ALIAS] = alias

        return value

    return validate


_TIMESPEC = vol.Schema({
    'days': cv.positive_int,
    'hours': cv.positive_int,
    'minutes': cv.positive_int,
    'seconds': cv.positive_int,
    'milliseconds': cv.positive_int,
})
_TIMESPEC_REQ = cv.has_at_least_one_key(
    'days', 'hours', 'minutes', 'seconds', 'milliseconds',
)

_DELAY_SCHEMA = vol.Any(
    vol.Schema({
        vol.Required(CONF_DELAY): vol.All(_TIMESPEC.extend({
            vol.Optional(CONF_ALIAS): cv.string
        }), _TIMESPEC_REQ)
    }),
    # Alternative format in case people forgot to indent after 'delay:'
    vol.All(_TIMESPEC.extend({
        vol.Required(CONF_DELAY): None,
        vol.Optional(CONF_ALIAS): cv.string,
    }), _TIMESPEC_REQ)
)

_EVENT_SCHEMA = cv.EVENT_SCHEMA.extend({
    CONF_ALIAS: cv.string,
})

_SCRIPT_ENTRY_SCHEMA = vol.Schema({
    CONF_ALIAS: cv.string,
    vol.Required(CONF_SEQUENCE): vol.All(vol.Length(min=1), [vol.Any(
        _EVENT_SCHEMA,
        _DELAY_SCHEMA,
        # Can't extend SERVICE_SCHEMA because it is an vol.All
        _alias_stripper(cv.SERVICE_SCHEMA),
    )]),
})

CONFIG_SCHEMA = vol.Schema({
    vol.Required(DOMAIN): {cv.slug: _SCRIPT_ENTRY_SCHEMA}
}, extra=vol.ALLOW_EXTRA)


def is_on(hass, entity_id):
    """Return if the switch is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id):
    """Turn script on."""
    _, object_id = split_entity_id(entity_id)

    hass.services.call(DOMAIN, object_id)


def turn_off(hass, entity_id):
    """Turn script on."""
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})


def toggle(hass, entity_id):
    """Toggle the script."""
    hass.services.call(DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id})


def setup(hass, config):
    """Load the scripts from the configuration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    def service_handler(service):
        """Execute a service call to script.<script name>."""
        entity_id = ENTITY_ID_FORMAT.format(service.service)
        script = component.entities.get(entity_id)
        if script.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        script.turn_on()

    for object_id, cfg in config[DOMAIN].items():
        alias = cfg.get(CONF_ALIAS, object_id)
        script = Script(object_id, alias, cfg[CONF_SEQUENCE])
        component.add_entities((script,))
        hass.services.register(DOMAIN, object_id, service_handler)

    def turn_on_service(service):
        """Call a service to turn script on."""
        # We could turn on script directly here, but we only want to offer
        # one way to do it. Otherwise no easy way to call invocations.
        for script in component.extract_from_service(service):
            turn_on(hass, script.entity_id)

    def turn_off_service(service):
        """Cancel a script."""
        for script in component.extract_from_service(service):
            script.turn_off()

    def toggle_service(service):
        """Toggle a script."""
        for script in component.extract_from_service(service):
            script.toggle()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, turn_on_service)
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, turn_off_service)
    hass.services.register(DOMAIN, SERVICE_TOGGLE, toggle_service)

    return True


class Script(ToggleEntity):
    """Representation of a script."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, object_id, name, sequence):
        """Initialize the script."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self.sequence = sequence
        self._lock = threading.Lock()
        self._cur = -1
        self._last_action = None
        self._listener = None
        self._can_cancel = any(CONF_DELAY in action for action
                               in self.sequence)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._can_cancel:
            attrs[ATTR_CAN_CANCEL] = self._can_cancel
        if self._last_action:
            attrs[ATTR_LAST_ACTION] = self._last_action
        return attrs

    @property
    def is_on(self):
        """Return true if script is on."""
        return self._cur != -1

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        _LOGGER.info("Executing script %s", self._name)
        with self._lock:
            if self._cur == -1:
                self._cur = 0

            # Unregister callback if we were in a delay but turn on is called
            # again. In that case we just continue execution.
            self._remove_listener()

            for cur, action in islice(enumerate(self.sequence), self._cur,
                                      None):

                if validate_service_call(action) is None:
                    self._call_service(action)

                elif CONF_EVENT in action:
                    self._fire_event(action)

                elif CONF_DELAY in action:
                    # Call ourselves in the future to continue work
                    def script_delay(now):
                        """Called after delay is done."""
                        self._listener = None
                        self.turn_on()

                    timespec = action[CONF_DELAY] or action.copy()
                    timespec.pop(CONF_DELAY, None)
                    delay = timedelta(**timespec)
                    self._listener = track_point_in_utc_time(
                        self.hass, script_delay, date_util.utcnow() + delay)
                    self._cur = cur + 1
                    self.update_ha_state()
                    return

            self._cur = -1
            self._last_action = None
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn script off."""
        _LOGGER.info("Cancelled script %s", self._name)
        with self._lock:
            if self._cur == -1:
                return

            self._cur = -1
            self.update_ha_state()
            self._remove_listener()

    def _call_service(self, action):
        """Call the service specified in the action."""
        self._last_action = action.get(CONF_ALIAS, 'call service')
        _LOGGER.info("Executing script %s step %s", self._name,
                     self._last_action)
        call_from_config(self.hass, action, True)

    def _fire_event(self, action):
        """Fire an event."""
        self._last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        _LOGGER.info("Executing script %s step %s", self._name,
                     self._last_action)
        self.hass.bus.fire(action[CONF_EVENT], action.get(CONF_EVENT_DATA))

    def _remove_listener(self):
        """Remove point in time listener, if any."""
        if self._listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._listener)
            self._listener = None
