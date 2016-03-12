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

import homeassistant.util.dt as date_util
from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity, split_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.service import call_from_config
from homeassistant.util import slugify

DOMAIN = "script"
ENTITY_ID_FORMAT = DOMAIN + '.{}'
DEPENDENCIES = ["group"]

STATE_NOT_RUNNING = 'Not Running'

CONF_ALIAS = "alias"
CONF_SERVICE = "service"
CONF_SERVICE_OLD = "execute_service"
CONF_SERVICE_DATA = "data"
CONF_SERVICE_DATA_OLD = "service_data"
CONF_SEQUENCE = "sequence"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_DELAY = "delay"

ATTR_LAST_ACTION = 'last_action'
ATTR_CAN_CANCEL = 'can_cancel'

_LOGGER = logging.getLogger(__name__)


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
        if not script:
            return
        if script.is_on:
            _LOGGER.warning("Script %s already running.", entity_id)
            return
        script.turn_on()

    for object_id, cfg in config[DOMAIN].items():
        if object_id != slugify(object_id):
            _LOGGER.warning("Found invalid key for script: %s. Use %s instead",
                            object_id, slugify(object_id))
            continue
        if not isinstance(cfg.get(CONF_SEQUENCE), list):
            _LOGGER.warning("Key 'sequence' for script %s should be a list",
                            object_id)
            continue
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

                if CONF_SERVICE in action or CONF_SERVICE_OLD in action:
                    self._call_service(action)

                elif CONF_EVENT in action:
                    self._fire_event(action)

                elif CONF_DELAY in action:
                    # Call ourselves in the future to continue work
                    def script_delay(now):
                        """Called after delay is done."""
                        self._listener = None
                        self.turn_on()

                    delay = timedelta(**action[CONF_DELAY])
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
        # Backwards compatibility
        if CONF_SERVICE not in action and CONF_SERVICE_OLD in action:
            action[CONF_SERVICE] = action[CONF_SERVICE_OLD]

        if CONF_SERVICE_DATA not in action and CONF_SERVICE_DATA_OLD in action:
            action[CONF_SERVICE_DATA] = action[CONF_SERVICE_DATA_OLD]

        self._last_action = action.get(CONF_ALIAS, action[CONF_SERVICE])
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
