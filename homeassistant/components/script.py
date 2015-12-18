"""
homeassistant.components.script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scripts are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/script/
"""
import logging
from datetime import timedelta
from itertools import islice
import threading

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util import slugify, split_entity_id
import homeassistant.util.dt as date_util
from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED, STATE_ON, SERVICE_TURN_ON,
    SERVICE_TURN_OFF)

DOMAIN = "script"
ENTITY_ID_FORMAT = DOMAIN + '.{}'
DEPENDENCIES = ["group"]

STATE_NOT_RUNNING = 'Not Running'

CONF_ALIAS = "alias"
CONF_SERVICE = "service"
CONF_SERVICE_OLD = "execute_service"
CONF_SERVICE_DATA = "service_data"
CONF_SEQUENCE = "sequence"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_DELAY = "delay"

ATTR_LAST_ACTION = 'last_action'
ATTR_CAN_CANCEL = 'can_cancel'

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id):
    """ Returns if the switch is on based on the statemachine. """
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id):
    """ Turn script on. """
    _, object_id = split_entity_id(entity_id)

    hass.services.call(DOMAIN, object_id)


def turn_off(hass, entity_id):
    """ Turn script on. """
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})


def setup(hass, config):
    """ Load the scripts from the configuration. """

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    def service_handler(service):
        """ Execute a service call to script.<script name>. """
        entity_id = ENTITY_ID_FORMAT.format(service.service)
        script = component.entities.get(entity_id)
        if script:
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
        script = Script(hass, object_id, alias, cfg[CONF_SEQUENCE])
        component.add_entities((script,))
        hass.services.register(DOMAIN, object_id, service_handler)

    def turn_on_service(service):
        """ Calls a service to turn script on. """
        # We could turn on script directly here, but we only want to offer
        # one way to do it. Otherwise no easy way to call invocations.
        for script in component.extract_from_service(service):
            turn_on(hass, script.entity_id)

    def turn_off_service(service):
        """ Cancels a script. """
        for script in component.extract_from_service(service):
            script.turn_off()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, turn_on_service)
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, turn_off_service)

    return True


class Script(ToggleEntity):
    """ Represents a script. """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, object_id, name, sequence):
        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self.sequence = sequence
        self._lock = threading.Lock()
        self._cur = -1
        self._last_action = None
        self._listener = None
        self._can_cancel = not any(CONF_DELAY in action for action
                                   in self.sequence)

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        """ Returns the name of the entity. """
        return self._name

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        attrs = {
            ATTR_CAN_CANCEL: self._can_cancel
        }

        if self._last_action:
            attrs[ATTR_LAST_ACTION] = self._last_action

        return attrs

    @property
    def is_on(self):
        """ True if entity is on. """
        return self._cur != -1

    def turn_on(self, **kwargs):
        """ Turn the entity on. """
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
                        """ Called after delay is done. """
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
        """ Turn script off. """
        _LOGGER.info("Cancelled script %s", self._name)
        with self._lock:
            if self._cur == -1:
                return

            self._cur = -1
            self.update_ha_state()
            self._remove_listener()

    def _call_service(self, action):
        """ Calls the service specified in the action. """
        conf_service = action.get(CONF_SERVICE, action.get(CONF_SERVICE_OLD))
        self._last_action = action.get(CONF_ALIAS, conf_service)
        _LOGGER.info("Executing script %s step %s", self._name,
                     self._last_action)
        domain, service = split_entity_id(conf_service)
        data = action.get(CONF_SERVICE_DATA, {})
        self.hass.services.call(domain, service, data, True)

    def _fire_event(self, action):
        """ Fires an event. """
        self._last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        _LOGGER.info("Executing script %s step %s", self._name,
                     self._last_action)
        self.hass.bus.fire(action[CONF_EVENT], action.get(CONF_EVENT_DATA))

    def _remove_listener(self):
        """ Remove point in time listener, if any. """
        if self._listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._listener)
            self._listener = None
