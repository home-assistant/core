"""
homeassistant.components.script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scripts are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.
"""
import logging
from datetime import datetime, timedelta
import threading

from homeassistant.util import split_entity_id
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF, EVENT_TIME_CHANGED)

DOMAIN = "script"
DEPENDENCIES = ["group"]

CONF_ALIAS = "alias"
CONF_SERVICE = "execute_service"
CONF_SERVICE_DATA = "service_data"
CONF_SEQUENCE = "sequence"
CONF_DELAY = "delay"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Load the scripts from the configuration. """

    scripts = []
    for name, cfg in config[DOMAIN].items():
        if CONF_SEQUENCE not in cfg:
            _LOGGER.warn("Missing key 'sequence' for script %s", name)
            continue
        alias = cfg.get(CONF_ALIAS, name)
        entity_id = "{}.{}".format(DOMAIN, name)
        script = Script(hass, entity_id, alias, cfg[CONF_SEQUENCE])
        hass.services.register(DOMAIN, name, script)
        scripts.append(script)

    def turn_on(service):
        """ Calls a script. """
        for entity_id in service.data['entity_id']:
            domain, service = split_entity_id(entity_id)
            hass.services.call(domain, service, {})

    def turn_off(service):
        """ Cancels a script. """
        for entity_id in service.data['entity_id']:
            for script in scripts:
                if script.entity_id == entity_id:
                    script.cancel()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, turn_on)
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, turn_off)

    return True


class Script(object):
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods
    """
    A script contains a sequence of service calls or configured delays
    that are executed in order.
    Each script also has a state (on/off) indicating whether the script is
    running or not.
    """
    def __init__(self, hass, entity_id, alias, sequence):
        self.hass = hass
        self.alias = alias
        self.sequence = sequence
        self.entity_id = entity_id
        self._lock = threading.Lock()
        self._reset()

    def cancel(self):
        """ Cancels a running script and resets the state back to off. """
        _LOGGER.info("Cancelled script %s", self.alias)
        with self._lock:
            if self.listener:
                self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                              self.listener)
                self.listener = None
            self._reset()

    def _reset(self):
        """ Resets a script back to default state so that it is ready to
            run from the start again. """
        self.actions = None
        self.listener = None
        self.last_action = "Not Running"
        self.hass.states.set(self.entity_id, STATE_OFF, {
            "friendly_name": self.alias,
            "last_action": self.last_action
        })

    def _execute_until_done(self):
        """ Executes a sequence of actions until finished or until a delay
            is encountered.  If a delay action is encountered, the script
            registers itself to be called again in the future, when
            _execute_until_done will resume.

            Returns True if finished, False otherwise. """
        for action in self.actions:
            if CONF_SERVICE in action:
                self._call_service(action)
            elif CONF_DELAY in action:
                delay = timedelta(**action[CONF_DELAY])
                point_in_time = datetime.now() + delay
                self.listener = self.hass.track_point_in_time(
                    self, point_in_time)
                return False
        return True

    def __call__(self, *args, **kwargs):
        """ Executes the script. """
        _LOGGER.info("Executing script %s", self.alias)
        with self._lock:
            if self.actions is None:
                self.actions = (action for action in self.sequence)

            if not self._execute_until_done():
                state = self.hass.states.get(self.entity_id)
                state.attributes['last_action'] = self.last_action
                self.hass.states.set(self.entity_id, STATE_ON,
                                     state.attributes)
            else:
                self._reset()

    def _call_service(self, action):
        """ Calls the service specified in the action. """
        self.last_action = action.get(CONF_ALIAS, action[CONF_SERVICE])
        _LOGGER.info("Executing script %s step %s", self.alias,
                     self.last_action)
        domain, service = split_entity_id(action[CONF_SERVICE])
        data = action.get(CONF_SERVICE_DATA, {})
        self.hass.services.call(domain, service, data)
