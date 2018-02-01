"""Helpers to execute scripts."""
import asyncio
import logging
from itertools import islice
from typing import Optional, Sequence

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_CONDITION, CONF_TIMEOUT
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import (
    service, condition, template as template,
    config_validation as cv)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_template)
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as date_util
from homeassistant.util.async import (
    run_coroutine_threadsafe, run_callback_threadsafe)

_LOGGER = logging.getLogger(__name__)

CONF_ALIAS = 'alias'
CONF_SERVICE = 'service'
CONF_SERVICE_DATA = 'data'
CONF_SEQUENCE = 'sequence'
CONF_EVENT = 'event'
CONF_EVENT_DATA = 'event_data'
CONF_EVENT_DATA_TEMPLATE = 'event_data_template'
CONF_DELAY = 'delay'
CONF_WAIT_TEMPLATE = 'wait_template'


def call_from_config(hass: HomeAssistant, config: ConfigType,
                     variables: Optional[Sequence]=None) -> None:
    """Call a script based on a config entry."""
    Script(hass, cv.SCRIPT_SCHEMA(config)).run(variables)


class Script():
    """Representation of a script."""

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
        self.last_triggered = None
        self.can_cancel = any(CONF_DELAY in action or CONF_WAIT_TEMPLATE
                              in action for action in self.sequence)
        self._async_listener = []
        self._template_cache = {}
        self._config_cache = {}

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
        self.last_triggered = date_util.utcnow()
        if self._cur == -1:
            self._log('Running script')
            self._cur = 0

        # Unregister callback if we were in a delay or wait but turn on is
        # called again. In that case we just continue execution.
        self._async_remove_listener()

        for cur, action in islice(enumerate(self.sequence), self._cur, None):

            if CONF_DELAY in action:
                # Call ourselves in the future to continue work
                unsub = None

                @callback
                def async_script_delay(now):
                    """Handle delay."""
                    # pylint: disable=cell-var-from-loop
                    self._async_listener.remove(unsub)
                    self.hass.async_add_job(self.async_run(variables))

                delay = action[CONF_DELAY]

                if isinstance(delay, template.Template):
                    delay = vol.All(
                        cv.time_period,
                        cv.positive_timedelta)(
                            delay.async_render(variables))

                unsub = async_track_point_in_utc_time(
                    self.hass, async_script_delay,
                    date_util.utcnow() + delay
                )
                self._async_listener.append(unsub)

                self._cur = cur + 1
                if self._change_listener:
                    self.hass.async_add_job(self._change_listener)
                return

            elif CONF_WAIT_TEMPLATE in action:
                # Call ourselves in the future to continue work
                wait_template = action[CONF_WAIT_TEMPLATE]
                wait_template.hass = self.hass

                # check if condition already okay
                if condition.async_template(
                        self.hass, wait_template, variables):
                    continue

                @callback
                def async_script_wait(entity_id, from_s, to_s):
                    """Handle script after template condition is true."""
                    self._async_remove_listener()
                    self.hass.async_add_job(self.async_run(variables))

                self._async_listener.append(async_track_template(
                    self.hass, wait_template, async_script_wait, variables))

                self._cur = cur + 1
                if self._change_listener:
                    self.hass.async_add_job(self._change_listener)

                if CONF_TIMEOUT in action:
                    self._async_set_timeout(action, variables)

                return

            elif CONF_CONDITION in action:
                if not self._async_check_condition(action, variables):
                    break

            elif CONF_EVENT in action:
                self._async_fire_event(action, variables)

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

    def _async_fire_event(self, action, variables):
        """Fire an event."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        self._log("Executing step %s" % self.last_action)
        event_data = dict(action.get(CONF_EVENT_DATA, {}))
        if CONF_EVENT_DATA_TEMPLATE in action:
            try:
                event_data.update(template.render_complex(
                    action[CONF_EVENT_DATA_TEMPLATE], variables))
            except TemplateError as ex:
                _LOGGER.error('Error rendering event data template: %s', ex)

        self.hass.bus.async_fire(action[CONF_EVENT],
                                 event_data)

    def _async_check_condition(self, action, variables):
        """Test if condition is matching."""
        config_cache_key = frozenset((k, str(v)) for k, v in action.items())
        config = self._config_cache.get(config_cache_key)
        if not config:
            config = condition.async_from_config(action, False)
            self._config_cache[config_cache_key] = config

        self.last_action = action.get(CONF_ALIAS, action[CONF_CONDITION])
        check = config(self.hass, variables)
        self._log("Test condition {}: {}".format(self.last_action, check))
        return check

    def _async_set_timeout(self, action, variables):
        """Schedule a timeout to abort script."""
        timeout = action[CONF_TIMEOUT]
        unsub = None

        @callback
        def async_script_timeout(now):
            """Call after timeout is retrieve stop script."""
            self._async_listener.remove(unsub)
            self._log("Timeout reached, abort script.")
            self.async_stop()

        unsub = async_track_point_in_utc_time(
            self.hass, async_script_timeout,
            date_util.utcnow() + timeout
        )
        self._async_listener.append(unsub)

    def _async_remove_listener(self):
        """Remove point in time listener, if any."""
        for unsub in self._async_listener:
            unsub()
        self._async_listener.clear()

    def _log(self, msg):
        """Logger helper."""
        if self.name is not None:
            msg = "Script {}: {}".format(self.name, msg)

        _LOGGER.info(msg)
