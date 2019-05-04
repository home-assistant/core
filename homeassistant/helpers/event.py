"""Helpers for listening to events."""
import functools as ft
import logging
from datetime import timedelta
from typing import Any, Callable, Mapping, Optional, Union

import attr
import voluptuous as vol

from ..const import (
    ATTR_NOW, EVENT_CORE_CONFIG_UPDATE, EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED, MATCH_ALL, SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET)
from ..core import Event, HomeAssistant, State, callback
from ..exceptions import TemplateError
from ..loader import bind_hass
from ..util import dt as dt_util
from ..util.async_ import run_callback_threadsafe
from . import config_validation as cv
from .sun import get_astral_event_next
from .template import Template
from .typing import TemplateVarsType

_LOGGER = logging.getLogger(__name__)

# PyLint does not like the use of threaded_listener_factory
# pylint: disable=invalid-name


def threaded_listener_factory(async_factory):
    """Convert an async event helper to a threaded one."""
    @ft.wraps(async_factory)
    def factory(*args, **kwargs):
        """Call async event helper safely."""
        hass = args[0]

        if not isinstance(hass, HomeAssistant):
            raise TypeError('First parameter needs to be a hass instance')

        async_remove = run_callback_threadsafe(
            hass.loop, ft.partial(async_factory, *args, **kwargs)).result()

        def remove():
            """Threadsafe removal."""
            run_callback_threadsafe(hass.loop, async_remove).result()

        return remove

    return factory


@callback
@bind_hass
def async_track_state_change(hass, entity_ids, action, from_state=None,
                             to_state=None):
    """Track specific state changes.

    entity_ids, from_state and to_state can be string or list.
    Use list to match multiple.

    Returns a function that can be called to remove the listener.

    Must be run within the event loop.
    """
    match_from_state = _process_state_match(from_state)
    match_to_state = _process_state_match(to_state)

    # Ensure it is a lowercase list with entity ids we want to match on
    if entity_ids == MATCH_ALL:
        pass
    elif isinstance(entity_ids, str):
        entity_ids = (entity_ids.lower(),)
    else:
        entity_ids = tuple(entity_id.lower() for entity_id in entity_ids)

    @callback
    def state_change_listener(event):
        """Handle specific state changes."""
        if entity_ids != MATCH_ALL and \
           event.data.get('entity_id') not in entity_ids:
            return

        old_state = event.data.get('old_state')
        if old_state is not None:
            old_state = old_state.state

        new_state = event.data.get('new_state')
        if new_state is not None:
            new_state = new_state.state

        if match_from_state(old_state) and match_to_state(new_state):
            hass.async_run_job(action, event.data.get('entity_id'),
                               event.data.get('old_state'),
                               event.data.get('new_state'))

    return hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)


track_state_change = threaded_listener_factory(async_track_state_change)


_boolean_coerce = vol.Any(cv.boolean, lambda val: False)


@callback
@bind_hass
def async_track_template(
        hass: HomeAssistant,
        template: Template,
        action: Callable[[str, Optional[State], Optional[State]], None],
        variables: Optional[TemplateVarsType] = None) \
        -> Callable[[], None]:
    """Add a listener that fires when a a template evaluates to 'true'.

    Listen for the result of the template becomming true, or a true-like
    string result, such as 'On', 'Open', or 'Yes'. If the template results
    in an error state when the value changes, this will be logged and not
    passed through.

    On template registration, the action will be called with an entity_id
    and state of some entity referenced by the template, or '*' if no
    entity is referenced by the template.

    If the initial run of the template is invalid and results in an
    exception, the listener will still be registered but will only
    fire if the template result becomes true without an exception.

    Action arguments
    ----------------
    entity_id
        ID of the entity that triggered the state change.
    old_state
        The old state of the entity that changed.
    new_state
        New state of the entity that changed.

    Parameters
    ----------
    hass
        Home assistant object.
    template
        The template to calculate.
    action
        Callable to call with results. See above for arguments.
    variables
        Variables to pass to the template.

    Returns
    -------
    Callable to unregister the listener.

    """
    @callback
    def state_changed_listener(event, template, last_result, result):
        """Check if condition is correct and run action."""
        if isinstance(result, TemplateError):
            _LOGGER.exception(result)
            return

        # These really should use the new `cv.boolean_coerce`
        # validator as per #23293 rather than have potential exceptions
        # thrown. Change once #23293 merged.
        if last_result is not None:
            if not _boolean_coerce(last_result) \
                    and _boolean_coerce(result):
                hass.async_run_job(action, event.data.get('entity_id'),
                                   event.data.get('old_state'),
                                   event.data.get('new_state'))
        elif _boolean_coerce(result):
            # First run of the listener. Figure out an entity ID to
            # pass back to the action because it expects one.
            info = template.async_render_to_info(variables)
            state = None
            entity_id = None
            #  pylint: disable=protected-access
            for eid in info._entities:
                state = hass.states.get(eid)
                if state:
                    entity_id = eid
                    break
            if not state:
                for st in hass.states.async_all():
                    if info.filter_lifecycle(st.entity_id):
                        state = st
                        entity_id = st.entity_id
                        break
            hass.async_run_job(
                action, entity_id or MATCH_ALL, state, state)

    info = async_track_template_result(
        hass, template, state_changed_listener, variables)

    return info.async_remove


track_template = threaded_listener_factory(async_track_template)


class TrackTemplateResultInfo:
    """Return value from async_track_template_result."""

    def __init__(self, hass, template, action, variables):
        """Initialiser, should be package private."""
        self.hass = hass
        self._template = template
        self._action = action
        self._variables = variables

        self._cancel = hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._state_changed_listener)

        self._info = template.async_render_to_info(variables)
        try:
            self._last_result = self._info.result
        except TemplateError as ex:
            self._last_result = None
            self._last_exception = True
            self.hass.async_run_job(
                self._action, None, self._template,
                None, ex)
        else:
            self._last_exception = False
            self.hass.async_run_job(
                self._action, None, self._template,
                None, self._last_result)

    @callback
    def async_remove(self) -> None:
        """Cancel the listener."""
        self._cancel()

    @callback
    def async_refresh(self) -> None:
        """Force recalculate the template."""
        self._refresh()

    @callback
    def _state_changed_listener(self, event):
        """Check if condition is correct and run action."""
        entity_id = event.data.get('entity_id')
        # Optimisation: if the old and new states are not None then this is
        # a state change rather than a life-cycle event, and therefore we
        # only need to check the include entities.
        old_state = event.data.get('old_state')
        new_state = event.data.get('new_state')
        if old_state is not None and new_state is not None:
            if not self._info.filter(entity_id):
                return
        elif not self._info.filter_lifecycle(entity_id):
            return

        self._refresh(event)

    def _refresh(self, event=None) -> None:
        self._info = self._template.async_render_to_info(self._variables)

        try:
            result = self._info.result
        except TemplateError as ex:
            if not self._last_exception:
                self.hass.async_run_job(
                    self._action, event, self._template,
                    self._last_result, ex)
            self._last_exception = True
            return
        self._last_exception = False

        # Check to see if the result has changed
        if result == self._last_result:
            return

        self.hass.async_run_job(
            self._action, event, self._template,
            self._last_result, result)
        self._last_result = result


TrackTemplateResultListener = Callable[[
    Optional[Event],
    Template,
    Optional[str],
    Union[str, TemplateError]], None]
"""Type for the listener for template results.

    Action arguments
    ----------------
    event
        Event that caused the template to change output. None if not
        triggered by an event.
    template
        The template that has changed.
    last_result
        The output from the template on the last successful run, or None
        if no previous successful run.
    result
        Result from the template run. This will be a string or an
        TemplateError if the template resulted in an error.
"""


@callback
@bind_hass
def async_track_template_result(
        hass: HomeAssistant,
        template: Template,
        action: TrackTemplateResultListener,
        variables: Optional[Mapping[str, Any]] = None) \
        -> TrackTemplateResultInfo:
    """Add a listener that fires when a the result of a template changes.

    The action will fire with the initial result from the template, and
    then whenever the output from the template changes. The template will
    be reevaluated if any states referenced in the last run of the
    template change, or if manually triggered. If the result of the
    evaluation is different from the previous run, the listener is passed
    the result.

    If the template results in an TemplateError, this will be returned to
    the listener the first time this happens but not for subsequent errors.
    Once the template returns to a non-error condition the result is sent
    to the action as usual.

    Parameters
    ----------
    hass
        Home assistant object.
    template
        The template to calculate.
    action
        Callable to call with results.
    variables
        Variables to pass to the template.

    Returns
    -------
    Info object used to unregister the listener, and refresh the template.

    """
    return TrackTemplateResultInfo(hass, template, action, variables)


@callback
@bind_hass
def async_track_same_state(hass, period, action, async_check_same_func,
                           entity_ids=MATCH_ALL):
    """Track the state of entities for a period and run an action.

    If async_check_func is None it use the state of orig_value.
    Without entity_ids we track all state changes.
    """
    async_remove_state_for_cancel = None
    async_remove_state_for_listener = None

    @callback
    def clear_listener():
        """Clear all unsub listener."""
        nonlocal async_remove_state_for_cancel, async_remove_state_for_listener

        if async_remove_state_for_listener is not None:
            async_remove_state_for_listener()
            async_remove_state_for_listener = None
        if async_remove_state_for_cancel is not None:
            async_remove_state_for_cancel()
            async_remove_state_for_cancel = None

    @callback
    def state_for_listener(now):
        """Fire on state changes after a delay and calls action."""
        nonlocal async_remove_state_for_listener
        async_remove_state_for_listener = None
        clear_listener()
        hass.async_run_job(action)

    @callback
    def state_for_cancel_listener(entity, from_state, to_state):
        """Fire on changes and cancel for listener if changed."""
        if not async_check_same_func(entity, from_state, to_state):
            clear_listener()

    async_remove_state_for_listener = async_track_point_in_utc_time(
        hass, state_for_listener, dt_util.utcnow() + period)

    async_remove_state_for_cancel = async_track_state_change(
        hass, entity_ids, state_for_cancel_listener)

    return clear_listener


track_same_state = threaded_listener_factory(async_track_same_state)


@callback
@bind_hass
def async_track_point_in_time(hass, action, point_in_time):
    """Add a listener that fires once after a specific point in time."""
    utc_point_in_time = dt_util.as_utc(point_in_time)

    @callback
    def utc_converter(utc_now):
        """Convert passed in UTC now to local now."""
        hass.async_run_job(action, dt_util.as_local(utc_now))

    return async_track_point_in_utc_time(hass, utc_converter,
                                         utc_point_in_time)


track_point_in_time = threaded_listener_factory(async_track_point_in_time)


@callback
@bind_hass
def async_track_point_in_utc_time(hass, action, point_in_time):
    """Add a listener that fires once after a specific point in UTC time."""
    # Ensure point_in_time is UTC
    point_in_time = dt_util.as_utc(point_in_time)

    @callback
    def point_in_time_listener(event):
        """Listen for matching time_changed events."""
        now = event.data[ATTR_NOW]

        if now < point_in_time or hasattr(point_in_time_listener, 'run'):
            return

        # Set variable so that we will never run twice.
        # Because the event bus might have to wait till a thread comes
        # available to execute this listener it might occur that the
        # listener gets lined up twice to be executed. This will make
        # sure the second time it does nothing.
        point_in_time_listener.run = True
        async_unsub()

        hass.async_run_job(action, now)

    async_unsub = hass.bus.async_listen(EVENT_TIME_CHANGED,
                                        point_in_time_listener)

    return async_unsub


track_point_in_utc_time = threaded_listener_factory(
    async_track_point_in_utc_time)


@callback
@bind_hass
def async_call_later(hass, delay, action):
    """Add a listener that is called in <delay>."""
    return async_track_point_in_utc_time(
        hass, action, dt_util.utcnow() + timedelta(seconds=delay))


call_later = threaded_listener_factory(
    async_call_later)


@callback
@bind_hass
def async_track_time_interval(hass, action, interval):
    """Add a listener that fires repetitively at every timedelta interval."""
    remove = None

    def next_interval():
        """Return the next interval."""
        return dt_util.utcnow() + interval

    @callback
    def interval_listener(now):
        """Handle elapsed intervals."""
        nonlocal remove
        remove = async_track_point_in_utc_time(
            hass, interval_listener, next_interval())
        hass.async_run_job(action, now)

    remove = async_track_point_in_utc_time(
        hass, interval_listener, next_interval())

    def remove_listener():
        """Remove interval listener."""
        remove()

    return remove_listener


track_time_interval = threaded_listener_factory(async_track_time_interval)


@attr.s
class SunListener:
    """Helper class to help listen to sun events."""

    hass = attr.ib(type=HomeAssistant)
    action = attr.ib(type=Callable)
    event = attr.ib(type=str)
    offset = attr.ib(type=timedelta)
    _unsub_sun = attr.ib(default=None)
    _unsub_config = attr.ib(default=None)

    @callback
    def async_attach(self):
        """Attach a sun listener."""
        assert self._unsub_config is None

        self._unsub_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._handle_config_event)

        self._listen_next_sun_event()

    @callback
    def async_detach(self):
        """Detach the sun listener."""
        assert self._unsub_sun is not None
        assert self._unsub_config is not None

        self._unsub_sun()
        self._unsub_sun = None
        self._unsub_config()
        self._unsub_config = None

    @callback
    def _listen_next_sun_event(self):
        """Set up the sun event listener."""
        assert self._unsub_sun is None

        self._unsub_sun = async_track_point_in_utc_time(
            self.hass, self._handle_sun_event,
            get_astral_event_next(self.hass, self.event, offset=self.offset)
        )

    @callback
    def _handle_sun_event(self, _now):
        """Handle solar event."""
        self._unsub_sun = None
        self._listen_next_sun_event()
        self.hass.async_run_job(self.action)

    @callback
    def _handle_config_event(self, _event):
        """Handle core config update."""
        assert self._unsub_sun is not None
        self._unsub_sun()
        self._unsub_sun = None
        self._listen_next_sun_event()


@callback
@bind_hass
def async_track_sunrise(hass, action, offset=None):
    """Add a listener that will fire a specified offset from sunrise daily."""
    listener = SunListener(hass, action, SUN_EVENT_SUNRISE, offset)
    listener.async_attach()
    return listener.async_detach


track_sunrise = threaded_listener_factory(async_track_sunrise)


@callback
@bind_hass
def async_track_sunset(hass, action, offset=None):
    """Add a listener that will fire a specified offset from sunset daily."""
    listener = SunListener(hass, action, SUN_EVENT_SUNSET, offset)
    listener.async_attach()
    return listener.async_detach


track_sunset = threaded_listener_factory(async_track_sunset)


@callback
@bind_hass
def async_track_utc_time_change(hass, action,
                                hour=None, minute=None, second=None,
                                local=False):
    """Add a listener that will fire if time matches a pattern."""
    # We do not have to wrap the function with time pattern matching logic
    # if no pattern given
    if all(val is None for val in (hour, minute, second)):
        @callback
        def time_change_listener(event):
            """Fire every time event that comes in."""
            hass.async_run_job(action, event.data[ATTR_NOW])

        return hass.bus.async_listen(EVENT_TIME_CHANGED, time_change_listener)

    matching_seconds = dt_util.parse_time_expression(second, 0, 59)
    matching_minutes = dt_util.parse_time_expression(minute, 0, 59)
    matching_hours = dt_util.parse_time_expression(hour, 0, 23)

    next_time = None

    def calculate_next(now):
        """Calculate and set the next time the trigger should fire."""
        nonlocal next_time

        localized_now = dt_util.as_local(now) if local else now
        next_time = dt_util.find_next_time_expression_time(
            localized_now, matching_seconds, matching_minutes,
            matching_hours)

    # Make sure rolling back the clock doesn't prevent the timer from
    # triggering.
    last_now = None

    @callback
    def pattern_time_change_listener(event):
        """Listen for matching time_changed events."""
        nonlocal next_time, last_now

        now = event.data[ATTR_NOW]

        if last_now is None or now < last_now:
            # Time rolled back or next time not yet calculated
            calculate_next(now)

        last_now = now

        if next_time <= now:
            hass.async_run_job(action, dt_util.as_local(now) if local else now)
            calculate_next(now + timedelta(seconds=1))

    # We can't use async_track_point_in_utc_time here because it would
    # break in the case that the system time abruptly jumps backwards.
    # Our custom last_now logic takes care of resolving that scenario.
    return hass.bus.async_listen(EVENT_TIME_CHANGED,
                                 pattern_time_change_listener)


track_utc_time_change = threaded_listener_factory(async_track_utc_time_change)


@callback
@bind_hass
def async_track_time_change(hass, action, hour=None, minute=None, second=None):
    """Add a listener that will fire if UTC time matches a pattern."""
    return async_track_utc_time_change(hass, action, hour, minute, second,
                                       local=True)


track_time_change = threaded_listener_factory(async_track_time_change)


def _process_state_match(parameter):
    """Convert parameter to function that matches input against parameter."""
    if parameter is None or parameter == MATCH_ALL:
        return lambda _: True

    if isinstance(parameter, str) or not hasattr(parameter, '__iter__'):
        return lambda state: state == parameter

    parameter = tuple(parameter)
    return lambda state: state in parameter
