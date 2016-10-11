"""Helpers to execute scripts."""
import asyncio
import logging
from itertools import islice
from typing import Optional, Sequence

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_CONDITION
from homeassistant.helpers import (
    service, condition, template, config_validation as cv)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as date_util
from homeassistant.util.async import (
    run_coroutine_threadsafe, run_callback_threadsafe)

_LOGGER = logging.getLogger(__name__)

CONF_ALIAS = "alias"
CONF_SERVICE = "service"
CONF_SERVICE_DATA = "data"
CONF_SEQUENCE = "sequence"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_DELAY = "delay"


def call_from_config(hass: HomeAssistant, config: ConfigType,
                     variables: Optional[Sequence]=None) -> None:
    """Call a script based on a config entry."""
    Script(hass, cv.SCRIPT_SCHEMA(config)).run(variables)


class Script():
    """Representation of a script."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass: HomeAssistant, sequence, name: str=None,
                 change_listener=None) -> None:
        """Initialize the script."""
        self.hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self._change_listener = change_listener
        self._cur = -1
        self.last_action = None
        self.can_cancel = any(CONF_DELAY in action for action
                              in self.sequence)
        self._async_unsub_delay_listener = None
        self._template_cache = {}

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return self._cur != -1

    def run(self, variables=None):
        """Run script."""
        run_coroutine_threadsafe(
            self.async_run(variables), self.hass.loop).result()

    @asyncio.coroutine
    def async_run(self, variables: Optional[Sequence]=None) -> None:
        """Run script.

        This method is a coroutine.
        """
        if self._cur == -1:
            self._log('Running script')
            self._cur = 0

        # Unregister callback if we were in a delay but turn on is called
        # again. In that case we just continue execution.
        self._async_remove_listener()

        for cur, action in islice(enumerate(self.sequence), self._cur,
                                  None):

            if CONF_DELAY in action:
                # Call ourselves in the future to continue work
                @asyncio.coroutine
                def script_delay(now):
                    """Called after delay is done."""
                    self._async_unsub_delay_listener = None
                    self.hass.loop.create_task(self.async_run(variables))

                delay = action[CONF_DELAY]

                if isinstance(delay, template.Template):
                    delay = vol.All(
                        cv.time_period,
                        cv.positive_timedelta)(
                            delay.async_render())

                self._async_unsub_delay_listener = \
                    async_track_point_in_utc_time(
                        self.hass, script_delay,
                        date_util.utcnow() + delay)
                self._cur = cur + 1
                if self._change_listener:
                    self.hass.async_add_job(self._change_listener)
                return

            elif CONF_CONDITION in action:
                if not self._async_check_condition(action, variables):
                    break

            elif CONF_EVENT in action:
                self._async_fire_event(action)

            else:
                yield from self._async_call_service(action, variables)

        self._cur = -1
        self.last_action = None
        if self._change_listener:
            self.hass.async_add_job(self._change_listener)

    def stop(self) -> None:
        """Stop running script."""
        run_callback_threadsafe(self.hass.loop, self.async_stop).result()

    def async_stop(self) -> None:
        """Stop running script."""
        if self._cur == -1:
            return

        self._cur = -1
        self._async_remove_listener()
        if self._change_listener:
            self.hass.async_add_job(self._change_listener)

    @asyncio.coroutine
    def _async_call_service(self, action, variables):
        """Call the service specified in the action.

        This method is a coroutine.
        """
        self.last_action = action.get(CONF_ALIAS, 'call service')
        self._log("Executing step %s" % self.last_action)
        yield from service.async_call_from_config(
            self.hass, action, True, variables, validate_config=False)

    def _async_fire_event(self, action):
        """Fire an event."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        self._log("Executing step %s" % self.last_action)
        self.hass.bus.async_fire(action[CONF_EVENT],
                                 action.get(CONF_EVENT_DATA))

    def _async_check_condition(self, action, variables):
        """Test if condition is matching."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_CONDITION])
        check = condition.async_from_config(action, False)(
            self.hass, variables)
        self._log("Test condition {}: {}".format(self.last_action, check))
        return check

    def _async_remove_listener(self):
        """Remove point in time listener, if any."""
        if self._async_unsub_delay_listener:
            self._async_unsub_delay_listener()
            self._async_unsub_delay_listener = None

    def _log(self, msg):
        """Logger helper."""
        if self.name is not None:
            msg = "Script {}: {}".format(self.name, msg)

        _LOGGER.info(msg)
