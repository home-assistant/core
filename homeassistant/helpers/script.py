"""Helpers to execute scripts."""
import logging
import threading
from itertools import islice

import homeassistant.util.dt as date_util
from homeassistant.const import EVENT_TIME_CHANGED, CONF_CONDITION
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers import service, condition
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ALIAS = "alias"
CONF_SERVICE = "service"
CONF_SERVICE_DATA = "data"
CONF_SEQUENCE = "sequence"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_DELAY = "delay"


def call_from_config(hass, config, variables=None):
    """Call a script based on a config entry."""
    Script(hass, config).run(variables)


class Script():
    """Representation of a script."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, sequence, name=None, change_listener=None):
        """Initialize the script."""
        self.hass = hass
        self.sequence = cv.SCRIPT_SCHEMA(sequence)
        self.name = name
        self._change_listener = change_listener
        self._cur = -1
        self.last_action = None
        self.can_cancel = any(CONF_DELAY in action for action
                              in self.sequence)
        self._lock = threading.Lock()
        self._delay_listener = None

    @property
    def is_running(self):
        """Return true if script is on."""
        return self._cur != -1

    def run(self, variables=None):
        """Run script."""
        with self._lock:
            if self._cur == -1:
                self._log('Running script')
                self._cur = 0

            # Unregister callback if we were in a delay but turn on is called
            # again. In that case we just continue execution.
            self._remove_listener()

            for cur, action in islice(enumerate(self.sequence), self._cur,
                                      None):

                if CONF_DELAY in action:
                    # Call ourselves in the future to continue work
                    def script_delay(now):
                        """Called after delay is done."""
                        self._delay_listener = None
                        self.run(variables)

                    self._delay_listener = track_point_in_utc_time(
                        self.hass, script_delay,
                        date_util.utcnow() + action[CONF_DELAY])
                    self._cur = cur + 1
                    if self._change_listener:
                        self._change_listener()
                    return

                elif CONF_CONDITION in action:
                    if not self._check_condition(action, variables):
                        break

                elif CONF_EVENT in action:
                    self._fire_event(action)

                else:
                    self._call_service(action, variables)

            self._cur = -1
            self.last_action = None
            if self._change_listener:
                self._change_listener()

    def stop(self):
        """Stop running script."""
        with self._lock:
            if self._cur == -1:
                return

            self._cur = -1
            self._remove_listener()
            if self._change_listener:
                self._change_listener()

    def _call_service(self, action, variables):
        """Call the service specified in the action."""
        self.last_action = action.get(CONF_ALIAS, 'call service')
        self._log("Executing step %s" % self.last_action)
        service.call_from_config(self.hass, action, True, variables,
                                 validate_config=False)

    def _fire_event(self, action):
        """Fire an event."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        self._log("Executing step %s" % self.last_action)
        self.hass.bus.fire(action[CONF_EVENT], action.get(CONF_EVENT_DATA))

    def _check_condition(self, action, variables):
        """Test if condition is matching."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_CONDITION])
        check = condition.from_config(action)(self.hass, variables)
        self._log("Test condition {}: {}".format(self.last_action, check))
        return check

    def _remove_listener(self):
        """Remove point in time listener, if any."""
        if self._delay_listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._delay_listener)
            self._delay_listener = None

    def _log(self, msg):
        """Logger helper."""
        if self.name is not None:
            msg = "Script {}: {}".format(self.name, msg)

        _LOGGER.info(msg)
