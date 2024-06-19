"""Helpers for listening to events."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial, wraps
import logging
from random import randint
import time
from typing import TYPE_CHECKING, Any, Concatenate, Generic, TypeVar

from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    MATCH_ALL,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    # Explicit reexport of 'EventStateChangedData' for backwards compatibility
    EventStateChangedData as EventStateChangedData,  # noqa: PLC0414
    HassJob,
    HassJobType,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import TemplateError
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey

from . import frame
from .device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from .entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    EventEntityRegistryUpdatedData,
)
from .ratelimit import KeyedRateLimit
from .sun import get_astral_event_next
from .template import RenderInfo, Template, result_as_boolean
from .typing import TemplateVarsType

_TRACK_STATE_CHANGE_DATA: HassKey[_KeyedEventData[EventStateChangedData]] = HassKey(
    "track_state_change_data"
)
_TRACK_STATE_ADDED_DOMAIN_DATA: HassKey[_KeyedEventData[EventStateChangedData]] = (
    HassKey("track_state_added_domain_data")
)
_TRACK_STATE_REMOVED_DOMAIN_DATA: HassKey[_KeyedEventData[EventStateChangedData]] = (
    HassKey("track_state_removed_domain_data")
)
_TRACK_ENTITY_REGISTRY_UPDATED_DATA: HassKey[
    _KeyedEventData[EventEntityRegistryUpdatedData]
] = HassKey("track_entity_registry_updated_data")
_TRACK_DEVICE_REGISTRY_UPDATED_DATA: HassKey[
    _KeyedEventData[EventDeviceRegistryUpdatedData]
] = HassKey("track_device_registry_updated_data")

_ALL_LISTENER = "all"
_DOMAINS_LISTENER = "domains"
_ENTITIES_LISTENER = "entities"

_LOGGER = logging.getLogger(__name__)

# Used to spread async_track_utc_time_change listeners and DataUpdateCoordinator
# refresh cycles between RANDOM_MICROSECOND_MIN..RANDOM_MICROSECOND_MAX.
# The values have been determined experimentally in production testing, background
# in PR https://github.com/home-assistant/core/pull/82233
RANDOM_MICROSECOND_MIN = 50000
RANDOM_MICROSECOND_MAX = 500000

_TypedDictT = TypeVar("_TypedDictT", bound=Mapping[str, Any])


@dataclass(slots=True, frozen=True)
class _KeyedEventTracker(Generic[_TypedDictT]):
    """Class to track events by key."""

    key: HassKey[_KeyedEventData[_TypedDictT]]
    event_type: EventType[_TypedDictT] | str
    dispatcher_callable: Callable[
        [
            HomeAssistant,
            dict[str, list[HassJob[[Event[_TypedDictT]], Any]]],
            Event[_TypedDictT],
        ],
        None,
    ]
    filter_callable: Callable[
        [
            HomeAssistant,
            dict[str, list[HassJob[[Event[_TypedDictT]], Any]]],
            _TypedDictT,
        ],
        bool,
    ]


@dataclass(slots=True, frozen=True)
class _KeyedEventData(Generic[_TypedDictT]):
    """Class to track data for events by key."""

    listener: CALLBACK_TYPE
    callbacks: defaultdict[str, list[HassJob[[Event[_TypedDictT]], Any]]]


@dataclass(slots=True)
class TrackStates:
    """Class for keeping track of states being tracked.

    all_states: All states on the system are being tracked
    entities: Lowercased entities to track
    domains: Lowercased domains to track
    """

    all_states: bool
    entities: set[str]
    domains: set[str]


@dataclass(slots=True)
class TrackTemplate:
    """Class for keeping track of a template with variables.

    The template is template to calculate.
    The variables are variables to pass to the template.
    The rate_limit is a rate limit on how often the template is re-rendered.
    """

    template: Template
    variables: TemplateVarsType
    rate_limit: float | None = None


@dataclass(slots=True)
class TrackTemplateResult:
    """Class for result of template tracking.

    template
        The template that has changed.
    last_result
        The output from the template on the last successful run, or None
        if no previous successful run.
    result
        Result from the template run. This will be a string or an
        TemplateError if the template resulted in an error.
    """

    template: Template
    last_result: Any
    result: Any


def threaded_listener_factory[**_P](
    async_factory: Callable[Concatenate[HomeAssistant, _P], Any],
) -> Callable[Concatenate[HomeAssistant, _P], CALLBACK_TYPE]:
    """Convert an async event helper to a threaded one."""

    @wraps(async_factory)
    def factory(
        hass: HomeAssistant, *args: _P.args, **kwargs: _P.kwargs
    ) -> CALLBACK_TYPE:
        """Call async event helper safely."""
        if not isinstance(hass, HomeAssistant):
            raise TypeError("First parameter needs to be a hass instance")

        async_remove = run_callback_threadsafe(
            hass.loop, partial(async_factory, hass, *args, **kwargs)
        ).result()

        def remove() -> None:
            """Threadsafe removal."""
            run_callback_threadsafe(hass.loop, async_remove).result()

        return remove

    return factory


@callback
@bind_hass
def async_track_state_change(
    hass: HomeAssistant,
    entity_ids: str | Iterable[str],
    action: Callable[
        [str, State | None, State | None], Coroutine[Any, Any, None] | None
    ],
    from_state: str | Iterable[str] | None = None,
    to_state: str | Iterable[str] | None = None,
) -> CALLBACK_TYPE:
    """Track specific state changes.

    entity_ids, from_state and to_state can be string or list.
    Use list to match multiple.

    Returns a function that can be called to remove the listener.

    If entity_ids are not MATCH_ALL along with from_state and to_state
    being None, async_track_state_change_event should be used instead
    as it is slightly faster.

    This function is deprecated and will be removed in Home Assistant 2025.5.

    Must be run within the event loop.
    """
    frame.report(
        "calls `async_track_state_change` instead of `async_track_state_change_event`"
        " which is deprecated and will be removed in Home Assistant 2025.5",
        error_if_core=False,
    )

    if from_state is not None:
        match_from_state = process_state_match(from_state)
    if to_state is not None:
        match_to_state = process_state_match(to_state)

    # Ensure it is a lowercase list with entity ids we want to match on
    if entity_ids == MATCH_ALL:
        pass
    elif isinstance(entity_ids, str):
        entity_ids = (entity_ids.lower(),)
    else:
        entity_ids = tuple(entity_id.lower() for entity_id in entity_ids)

    job = HassJob(action, f"track state change {entity_ids} {from_state} {to_state}")

    @callback
    def state_change_filter(event_data: EventStateChangedData) -> bool:
        """Handle specific state changes."""
        if from_state is not None:
            old_state_str: str | None = None
            if (old_state := event_data["old_state"]) is not None:
                old_state_str = old_state.state

            if not match_from_state(old_state_str):
                return False

        if to_state is not None:
            new_state_str: str | None = None
            if (new_state := event_data["new_state"]) is not None:
                new_state_str = new_state.state

            if not match_to_state(new_state_str):
                return False

        return True

    @callback
    def state_change_dispatcher(event: Event[EventStateChangedData]) -> None:
        """Handle specific state changes."""
        hass.async_run_hass_job(
            job,
            event.data["entity_id"],
            event.data["old_state"],
            event.data["new_state"],
        )

    @callback
    def state_change_listener(event: Event[EventStateChangedData]) -> None:
        """Handle specific state changes."""
        if not state_change_filter(event.data):
            return

        state_change_dispatcher(event)

    if entity_ids != MATCH_ALL:
        # If we have a list of entity ids we use
        # async_track_state_change_event to route
        # by entity_id to avoid iterating though state change
        # events and creating a jobs where the most
        # common outcome is to return right away because
        # the entity_id does not match since usually
        # only one or two listeners want that specific
        # entity_id.
        return async_track_state_change_event(hass, entity_ids, state_change_listener)

    return hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        state_change_dispatcher,
        event_filter=state_change_filter,
    )


track_state_change = threaded_listener_factory(async_track_state_change)


@bind_hass
def async_track_state_change_event(
    hass: HomeAssistant,
    entity_ids: str | Iterable[str],
    action: Callable[[Event[EventStateChangedData]], Any],
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Track specific state change events indexed by entity_id.

    Unlike async_track_state_change, async_track_state_change_event
    passes the full event to the callback.

    In order to avoid having to iterate a long list
    of EVENT_STATE_CHANGED and fire and create a job
    for each one, we keep a dict of entity ids that
    care about the state change events so we can
    do a fast dict lookup to route events.
    """
    if not (entity_ids := _async_string_to_lower_list(entity_ids)):
        return _remove_empty_listener
    return _async_track_state_change_event(hass, entity_ids, action, job_type)


@callback
def _async_dispatch_entity_id_event(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventStateChangedData]], Any]]],
    event: Event[EventStateChangedData],
) -> None:
    """Dispatch to listeners."""
    if not (callbacks_list := callbacks.get(event.data["entity_id"])):
        return
    for job in callbacks_list.copy():
        try:
            hass.async_run_hass_job(job, event)
        except Exception:
            _LOGGER.exception(
                "Error while dispatching event for %s to %s",
                event.data["entity_id"],
                job,
            )


@callback
def _async_state_change_filter(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventStateChangedData]], Any]]],
    event_data: EventStateChangedData,
) -> bool:
    """Filter state changes by entity_id."""
    return event_data["entity_id"] in callbacks


_KEYED_TRACK_STATE_CHANGE = _KeyedEventTracker(
    key=_TRACK_STATE_CHANGE_DATA,
    event_type=EVENT_STATE_CHANGED,
    dispatcher_callable=_async_dispatch_entity_id_event,
    filter_callable=_async_state_change_filter,
)


@bind_hass
def _async_track_state_change_event(
    hass: HomeAssistant,
    entity_ids: str | Iterable[str],
    action: Callable[[Event[EventStateChangedData]], Any],
    job_type: HassJobType | None,
) -> CALLBACK_TYPE:
    """async_track_state_change_event without lowercasing."""
    return _async_track_event(
        _KEYED_TRACK_STATE_CHANGE, hass, entity_ids, action, job_type
    )


@callback
def _remove_empty_listener() -> None:
    """Remove a listener that does nothing."""


@callback
def _remove_listener(
    hass: HomeAssistant,
    tracker: _KeyedEventTracker[_TypedDictT],
    keys: Iterable[str],
    job: HassJob[[Event[_TypedDictT]], Any],
    callbacks: dict[str, list[HassJob[[Event[_TypedDictT]], Any]]],
) -> None:
    """Remove listener."""
    for key in keys:
        callbacks[key].remove(job)
        if not callbacks[key]:
            del callbacks[key]

    if not callbacks:
        hass.data.pop(tracker.key).listener()


# tracker, not hass is intentionally the first argument here since its
# constant and may be used in a partial in the future
def _async_track_event(
    tracker: _KeyedEventTracker[_TypedDictT],
    hass: HomeAssistant,
    keys: str | Iterable[str],
    action: Callable[[Event[_TypedDictT]], None],
    job_type: HassJobType | None,
) -> CALLBACK_TYPE:
    """Track an event by a specific key.

    This function is intended for internal use only.
    """
    if not keys:
        return _remove_empty_listener

    hass_data = hass.data
    tracker_key = tracker.key
    if tracker_key in hass_data:
        event_data = hass_data[tracker_key]
        callbacks = event_data.callbacks
    else:
        callbacks = defaultdict(list)
        listener = hass.bus.async_listen(
            tracker.event_type,
            partial(tracker.dispatcher_callable, hass, callbacks),
            event_filter=partial(tracker.filter_callable, hass, callbacks),
        )
        event_data = _KeyedEventData(listener, callbacks)
        hass_data[tracker_key] = event_data

    job = HassJob(action, f"track {tracker.event_type} event {keys}", job_type=job_type)

    if isinstance(keys, str):
        # Almost all calls to this function use a single key
        # so we optimize for that case. We don't use setdefault
        # here because this function gets called ~20000 times
        # during startup, and we want to avoid the overhead of
        # creating empty lists and throwing them away.
        callbacks[keys].append(job)
        keys = (keys,)
    else:
        for key in keys:
            callbacks[key].append(job)

    return partial(_remove_listener, hass, tracker, keys, job, callbacks)


@callback
def _async_dispatch_old_entity_id_or_entity_id_event(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventEntityRegistryUpdatedData]], Any]]],
    event: Event[EventEntityRegistryUpdatedData],
) -> None:
    """Dispatch to listeners."""
    if not (
        callbacks_list := callbacks.get(  # type: ignore[call-overload]  # mypy bug?
            event.data.get("old_entity_id", event.data["entity_id"])
        )
    ):
        return
    for job in callbacks_list.copy():
        try:
            hass.async_run_hass_job(job, event)
        except Exception:
            _LOGGER.exception(
                "Error while dispatching event for %s to %s",
                event.data.get("old_entity_id", event.data["entity_id"]),
                job,
            )


@callback
def _async_entity_registry_updated_filter(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventEntityRegistryUpdatedData]], Any]]],
    event_data: EventEntityRegistryUpdatedData,
) -> bool:
    """Filter entity registry updates by entity_id."""
    return event_data.get("old_entity_id", event_data["entity_id"]) in callbacks


_KEYED_TRACK_ENTITY_REGISTRY_UPDATED = _KeyedEventTracker(
    key=_TRACK_ENTITY_REGISTRY_UPDATED_DATA,
    event_type=EVENT_ENTITY_REGISTRY_UPDATED,
    dispatcher_callable=_async_dispatch_old_entity_id_or_entity_id_event,
    filter_callable=_async_entity_registry_updated_filter,
)


@bind_hass
@callback
def async_track_entity_registry_updated_event(
    hass: HomeAssistant,
    entity_ids: str | Iterable[str],
    action: Callable[[Event[EventEntityRegistryUpdatedData]], Any],
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Track specific entity registry updated events indexed by entity_id.

    Entities must be lower case.

    Similar to async_track_state_change_event.
    """
    return _async_track_event(
        _KEYED_TRACK_ENTITY_REGISTRY_UPDATED, hass, entity_ids, action, job_type
    )


@callback
def _async_device_registry_updated_filter(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventDeviceRegistryUpdatedData]], Any]]],
    event_data: EventDeviceRegistryUpdatedData,
) -> bool:
    """Filter device registry updates by device_id."""
    return event_data["device_id"] in callbacks


@callback
def _async_dispatch_device_id_event(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventDeviceRegistryUpdatedData]], Any]]],
    event: Event[EventDeviceRegistryUpdatedData],
) -> None:
    """Dispatch to listeners."""
    if not (callbacks_list := callbacks.get(event.data["device_id"])):
        return
    for job in callbacks_list.copy():
        try:
            hass.async_run_hass_job(job, event)
        except Exception:
            _LOGGER.exception(
                "Error while dispatching event for %s to %s",
                event.data["device_id"],
                job,
            )


_KEYED_TRACK_DEVICE_REGISTRY_UPDATED = _KeyedEventTracker(
    key=_TRACK_DEVICE_REGISTRY_UPDATED_DATA,
    event_type=EVENT_DEVICE_REGISTRY_UPDATED,
    dispatcher_callable=_async_dispatch_device_id_event,
    filter_callable=_async_device_registry_updated_filter,
)


@callback
def async_track_device_registry_updated_event(
    hass: HomeAssistant,
    device_ids: str | Iterable[str],
    action: Callable[[Event[EventDeviceRegistryUpdatedData]], Any],
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Track specific device registry updated events indexed by device_id.

    Similar to async_track_entity_registry_updated_event.
    """
    return _async_track_event(
        _KEYED_TRACK_DEVICE_REGISTRY_UPDATED, hass, device_ids, action, job_type
    )


@callback
def _async_dispatch_domain_event(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventStateChangedData]], Any]]],
    event: Event[EventStateChangedData],
) -> None:
    """Dispatch domain event listeners."""
    domain = split_entity_id(event.data["entity_id"])[0]
    for job in callbacks.get(domain, []) + callbacks.get(MATCH_ALL, []):
        try:
            hass.async_run_hass_job(job, event)
        except Exception:
            _LOGGER.exception(
                "Error while processing event %s for domain %s", event, domain
            )


@callback
def _async_domain_added_filter(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventStateChangedData]], Any]]],
    event_data: EventStateChangedData,
) -> bool:
    """Filter state changes by entity_id."""
    return event_data["old_state"] is None and (
        MATCH_ALL in callbacks
        or
        # If old_state is None, new_state must be set but
        # mypy doesn't know that
        event_data["new_state"].domain in callbacks  # type: ignore[union-attr]
    )


@bind_hass
def async_track_state_added_domain(
    hass: HomeAssistant,
    domains: str | Iterable[str],
    action: Callable[[Event[EventStateChangedData]], Any],
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Track state change events when an entity is added to domains."""
    if not (domains := _async_string_to_lower_list(domains)):
        return _remove_empty_listener
    return _async_track_state_added_domain(hass, domains, action, job_type)


_KEYED_TRACK_STATE_ADDED_DOMAIN = _KeyedEventTracker(
    key=_TRACK_STATE_ADDED_DOMAIN_DATA,
    event_type=EVENT_STATE_CHANGED,
    dispatcher_callable=_async_dispatch_domain_event,
    filter_callable=_async_domain_added_filter,
)


@bind_hass
def _async_track_state_added_domain(
    hass: HomeAssistant,
    domains: str | Iterable[str],
    action: Callable[[Event[EventStateChangedData]], Any],
    job_type: HassJobType | None,
) -> CALLBACK_TYPE:
    """Track state change events when an entity is added to domains."""
    return _async_track_event(
        _KEYED_TRACK_STATE_ADDED_DOMAIN, hass, domains, action, job_type
    )


@callback
def _async_domain_removed_filter(
    hass: HomeAssistant,
    callbacks: dict[str, list[HassJob[[Event[EventStateChangedData]], Any]]],
    event_data: EventStateChangedData,
) -> bool:
    """Filter state changes by entity_id."""
    return event_data["new_state"] is None and (
        MATCH_ALL in callbacks
        or
        # If new_state is None, old_state must be set but
        # mypy doesn't know that
        event_data["old_state"].domain in callbacks  # type: ignore[union-attr]
    )


_KEYED_TRACK_STATE_REMOVED_DOMAIN = _KeyedEventTracker(
    key=_TRACK_STATE_REMOVED_DOMAIN_DATA,
    event_type=EVENT_STATE_CHANGED,
    dispatcher_callable=_async_dispatch_domain_event,
    filter_callable=_async_domain_removed_filter,
)


@bind_hass
def async_track_state_removed_domain(
    hass: HomeAssistant,
    domains: str | Iterable[str],
    action: Callable[[Event[EventStateChangedData]], Any],
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Track state change events when an entity is removed from domains."""
    return _async_track_event(
        _KEYED_TRACK_STATE_REMOVED_DOMAIN, hass, domains, action, job_type
    )


@callback
def _async_string_to_lower_list(instr: str | Iterable[str]) -> list[str]:
    if isinstance(instr, str):
        return [instr.lower()]

    return [mstr.lower() for mstr in instr]


class _TrackStateChangeFiltered:
    """Handle removal / refresh of tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        track_states: TrackStates,
        action: Callable[[Event[EventStateChangedData]], Any],
    ) -> None:
        """Handle removal / refresh of tracker init."""
        self.hass = hass
        self._action = action
        self._action_as_hassjob = HassJob(
            action, f"track state change filtered {track_states}"
        )
        self._listeners: dict[str, Callable[[], None]] = {}
        self._last_track_states: TrackStates = track_states

    @callback
    def async_setup(self) -> None:
        """Create listeners to track states."""
        track_states = self._last_track_states

        if (
            not track_states.all_states
            and not track_states.domains
            and not track_states.entities
        ):
            return

        if track_states.all_states:
            self._setup_all_listener()
            return

        self._setup_domains_listener(track_states.domains)
        self._setup_entities_listener(track_states.domains, track_states.entities)

    @property
    def listeners(self) -> dict[str, bool | set[str]]:
        """State changes that will cause a re-render."""
        track_states = self._last_track_states
        return {
            _ALL_LISTENER: track_states.all_states,
            _ENTITIES_LISTENER: track_states.entities,
            _DOMAINS_LISTENER: track_states.domains,
        }

    @callback
    def async_update_listeners(self, new_track_states: TrackStates) -> None:
        """Update the listeners based on the new TrackStates."""
        last_track_states = self._last_track_states
        self._last_track_states = new_track_states

        had_all_listener = last_track_states.all_states

        if new_track_states.all_states:
            if had_all_listener:
                return
            self._cancel_listener(_DOMAINS_LISTENER)
            self._cancel_listener(_ENTITIES_LISTENER)
            self._setup_all_listener()
            return

        if had_all_listener:
            self._cancel_listener(_ALL_LISTENER)

        domains_changed = new_track_states.domains != last_track_states.domains

        if had_all_listener or domains_changed:
            domains_changed = True
            self._cancel_listener(_DOMAINS_LISTENER)
            self._setup_domains_listener(new_track_states.domains)

        if (
            had_all_listener
            or domains_changed
            or new_track_states.entities != last_track_states.entities
        ):
            self._cancel_listener(_ENTITIES_LISTENER)
            self._setup_entities_listener(
                new_track_states.domains, new_track_states.entities
            )

    @callback
    def async_remove(self) -> None:
        """Cancel the listeners."""
        for key in list(self._listeners):
            self._listeners.pop(key)()

    @callback
    def _cancel_listener(self, listener_name: str) -> None:
        if listener_name not in self._listeners:
            return

        self._listeners.pop(listener_name)()

    @callback
    def _setup_entities_listener(self, domains: set[str], entities: set[str]) -> None:
        if domains:
            entities = entities.copy()
            entities.update(self.hass.states.async_entity_ids(domains))

        # Entities has changed to none
        if not entities:
            return

        self._listeners[_ENTITIES_LISTENER] = _async_track_state_change_event(
            self.hass, entities, self._action, self._action_as_hassjob.job_type
        )

    @callback
    def _state_added(self, event: Event[EventStateChangedData]) -> None:
        self._cancel_listener(_ENTITIES_LISTENER)
        self._setup_entities_listener(
            self._last_track_states.domains, self._last_track_states.entities
        )
        self.hass.async_run_hass_job(self._action_as_hassjob, event)

    @callback
    def _setup_domains_listener(self, domains: set[str]) -> None:
        if not domains:
            return

        self._listeners[_DOMAINS_LISTENER] = _async_track_state_added_domain(
            self.hass, domains, self._state_added, HassJobType.Callback
        )

    @callback
    def _setup_all_listener(self) -> None:
        self._listeners[_ALL_LISTENER] = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._action
        )


@callback
@bind_hass
def async_track_state_change_filtered(
    hass: HomeAssistant,
    track_states: TrackStates,
    action: Callable[[Event[EventStateChangedData]], Any],
) -> _TrackStateChangeFiltered:
    """Track state changes with a TrackStates filter that can be updated.

    Parameters
    ----------
    hass
        Home assistant object.
    track_states
        A TrackStates data class.
    action
        Callable to call with results.

    Returns
    -------
    Object used to update the listeners (async_update_listeners) with a new
    TrackStates or cancel the tracking (async_remove).

    """
    tracker = _TrackStateChangeFiltered(hass, track_states, action)
    tracker.async_setup()
    return tracker


@callback
@bind_hass
def async_track_template(
    hass: HomeAssistant,
    template: Template,
    action: Callable[
        [str, State | None, State | None], Coroutine[Any, Any, None] | None
    ],
    variables: TemplateVarsType | None = None,
) -> CALLBACK_TYPE:
    """Add a listener that fires when a template evaluates to 'true'.

    Listen for the result of the template becoming true, or a true-like
    string result, such as 'On', 'Open', or 'Yes'. If the template results
    in an error state when the value changes, this will be logged and not
    passed through.

    If the initial check of the template is invalid and results in an
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
    job = HassJob(action, f"track template {template}")

    @callback
    def _template_changed_listener(
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Check if condition is correct and run action."""
        track_result = updates.pop()

        template = track_result.template
        last_result = track_result.last_result
        result = track_result.result

        if isinstance(result, TemplateError):
            _LOGGER.error(
                "Error while processing template: %s",
                template.template,
                exc_info=result,
            )
            return

        if (
            not isinstance(last_result, TemplateError)
            and result_as_boolean(last_result)
            or not result_as_boolean(result)
        ):
            return

        hass.async_run_hass_job(
            job,
            event and event.data["entity_id"],
            event and event.data["old_state"],
            event and event.data["new_state"],
        )

    info = async_track_template_result(
        hass, [TrackTemplate(template, variables)], _template_changed_listener
    )

    return info.async_remove


track_template = threaded_listener_factory(async_track_template)


class TrackTemplateResultInfo:
    """Handle removal / refresh of tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        track_templates: Sequence[TrackTemplate],
        action: TrackTemplateResultListener,
        has_super_template: bool = False,
    ) -> None:
        """Handle removal / refresh of tracker init."""
        self.hass = hass
        self._job = HassJob(action, f"track template result {track_templates}")

        for track_template_ in track_templates:
            track_template_.template.hass = hass
        self._track_templates = track_templates
        self._has_super_template = has_super_template

        self._last_result: dict[Template, bool | str | TemplateError] = {}

        self._rate_limit = KeyedRateLimit(hass)
        self._info: dict[Template, RenderInfo] = {}
        self._track_state_changes: _TrackStateChangeFiltered | None = None
        self._time_listeners: dict[Template, Callable[[], None]] = {}

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<TrackTemplateResultInfo {self._info}>"

    def async_setup(
        self,
        strict: bool = False,
        log_fn: Callable[[int, str], None] | None = None,
    ) -> None:
        """Activation of template tracking."""
        block_render = False
        super_template = self._track_templates[0] if self._has_super_template else None

        # Render the super template first
        if super_template is not None:
            template = super_template.template
            variables = super_template.variables
            self._info[template] = info = template.async_render_to_info(
                variables, strict=strict, log_fn=log_fn
            )

            # If the super template did not render to True, don't update other templates
            try:
                super_result: str | TemplateError = info.result()
            except TemplateError as ex:
                super_result = ex
            if (
                super_result is not None
                and self._super_template_as_boolean(super_result) is not True
            ):
                block_render = True

        # Then update the remaining templates unless blocked by the super template
        for track_template_ in self._track_templates:
            if block_render or track_template_ == super_template:
                continue
            template = track_template_.template
            variables = track_template_.variables
            self._info[template] = info = template.async_render_to_info(
                variables, strict=strict, log_fn=log_fn
            )

            if info.exception:
                if not log_fn:
                    _LOGGER.error(
                        "Error while processing template: %s",
                        track_template_.template,
                        exc_info=info.exception,
                    )
                else:
                    log_fn(logging.ERROR, str(info.exception))

        self._track_state_changes = async_track_state_change_filtered(
            self.hass, _render_infos_to_track_states(self._info.values()), self._refresh
        )
        self._update_time_listeners()
        _LOGGER.debug(
            (
                "Template group %s listens for %s, first render blocked by super"
                " template: %s"
            ),
            self._track_templates,
            self.listeners,
            block_render,
        )

    @property
    def listeners(self) -> dict[str, bool | set[str]]:
        """State changes that will cause a re-render."""
        assert self._track_state_changes
        return {
            **self._track_state_changes.listeners,
            "time": bool(self._time_listeners),
        }

    @callback
    def _setup_time_listener(self, template: Template, has_time: bool) -> None:
        if not has_time:
            if template in self._time_listeners:
                # now() or utcnow() has left the scope of the template
                self._time_listeners.pop(template)()
            return

        if template in self._time_listeners:
            return

        track_templates = [
            track_template_
            for track_template_ in self._track_templates
            if track_template_.template == template
        ]

        @callback
        def _refresh_from_time(now: datetime) -> None:
            self._refresh(None, track_templates=track_templates)

        self._time_listeners[template] = async_track_utc_time_change(
            self.hass, _refresh_from_time, second=0
        )

    @callback
    def _update_time_listeners(self) -> None:
        for template, info in self._info.items():
            self._setup_time_listener(template, info.has_time)

    @callback
    def async_remove(self) -> None:
        """Cancel the listener."""
        assert self._track_state_changes
        self._track_state_changes.async_remove()
        self._rate_limit.async_remove()
        for template in list(self._time_listeners):
            self._time_listeners.pop(template)()

    @callback
    def async_refresh(self) -> None:
        """Force recalculate the template."""
        self._refresh(None)

    def _render_template_if_ready(
        self,
        track_template_: TrackTemplate,
        now: float,
        event: Event[EventStateChangedData] | None,
    ) -> bool | TrackTemplateResult:
        """Re-render the template if conditions match.

        Returns False if the template was not re-rendered.

        Returns True if the template re-rendered and did not
        change.

        Returns TrackTemplateResult if the template re-render
        generates a new result.
        """
        template = track_template_.template

        if event:
            info = self._info[template]

            if not _event_triggers_rerender(event, info):
                return False

            had_timer = self._rate_limit.async_has_timer(template)

            if self._rate_limit.async_schedule_action(
                template,
                _rate_limit_for_event(event, info, track_template_),
                now,
                self._refresh,
                event,
                (track_template_,),
                True,
            ):
                return not had_timer

            _LOGGER.debug(
                "Template update %s triggered by event: %s",
                template.template,
                event,
            )

        self._rate_limit.async_triggered(template, now)
        self._info[template] = info = template.async_render_to_info(
            track_template_.variables
        )

        try:
            result: str | TemplateError = info.result()
        except TemplateError as ex:
            result = ex

        last_result = self._last_result.get(template)

        # Check to see if the result has changed or is new
        if result == last_result and template in self._last_result:
            return True

        if isinstance(result, TemplateError) and isinstance(last_result, TemplateError):
            return True

        return TrackTemplateResult(template, last_result, result)

    @staticmethod
    def _super_template_as_boolean(result: bool | str | TemplateError) -> bool:
        """Return True if the result is truthy or a TemplateError."""
        if isinstance(result, TemplateError):
            return True

        return result_as_boolean(result)

    @callback
    def _apply_update(
        self,
        updates: list[TrackTemplateResult],
        update: bool | TrackTemplateResult,
        template: Template,
    ) -> bool:
        """Handle updates of a tracked template."""
        if not update:
            return False

        self._setup_time_listener(template, self._info[template].has_time)

        if isinstance(update, TrackTemplateResult):
            updates.append(update)

        return True

    @callback
    def _refresh(
        self,
        event: Event[EventStateChangedData] | None,
        track_templates: Iterable[TrackTemplate] | None = None,
        replayed: bool | None = False,
    ) -> None:
        """Refresh the template.

        The event is the state_changed event that caused the refresh
        to be considered.

        track_templates is an optional list of TrackTemplate objects
        to refresh.  If not provided, all tracked templates will be
        considered.

        replayed is True if the event is being replayed because the
        rate limit was hit.
        """
        updates: list[TrackTemplateResult] = []
        info_changed = False
        now = event.time_fired_timestamp if not replayed and event else time.time()

        block_updates = False
        super_template = self._track_templates[0] if self._has_super_template else None

        track_templates = track_templates or self._track_templates

        # Update the super template first
        if super_template is not None:
            update = self._render_template_if_ready(super_template, now, event)
            info_changed |= self._apply_update(updates, update, super_template.template)

            if isinstance(update, TrackTemplateResult):
                super_result = update.result
            else:
                super_result = self._last_result.get(super_template.template)

            # If the super template did not render to True, don't update other templates
            if (
                super_result is not None
                and self._super_template_as_boolean(super_result) is not True
            ):
                block_updates = True

            if (
                isinstance(update, TrackTemplateResult)
                and self._super_template_as_boolean(update.last_result) is not True
                and self._super_template_as_boolean(update.result) is True
            ):
                # Super template changed from not True to True, force re-render
                # of all templates in the group
                event = None
                track_templates = self._track_templates

        # Then update the remaining templates unless blocked by the super template
        if not block_updates:
            for track_template_ in track_templates:
                if track_template_ == super_template:
                    continue

                update = self._render_template_if_ready(track_template_, now, event)
                info_changed |= self._apply_update(
                    updates, update, track_template_.template
                )

        if info_changed:
            assert self._track_state_changes
            self._track_state_changes.async_update_listeners(
                _render_infos_to_track_states(
                    [
                        _suppress_domain_all_in_render_info(info)
                        if self._rate_limit.async_has_timer(template)
                        else info
                        for template, info in self._info.items()
                    ]
                )
            )
            _LOGGER.debug(
                (
                    "Template group %s listens for %s, re-render blocked by super"
                    " template: %s"
                ),
                self._track_templates,
                self.listeners,
                block_updates,
            )

        if not updates:
            return

        for track_result in updates:
            self._last_result[track_result.template] = track_result.result

        self.hass.async_run_hass_job(self._job, event, updates)


type TrackTemplateResultListener = Callable[
    [
        Event[EventStateChangedData] | None,
        list[TrackTemplateResult],
    ],
    Coroutine[Any, Any, None] | None,
]
"""Type for the listener for template results.

    Action arguments
    ----------------
    event
        Event that caused the template to change output. None if not
        triggered by an event.
    updates
        A list of TrackTemplateResult
"""


@callback
@bind_hass
def async_track_template_result(
    hass: HomeAssistant,
    track_templates: Sequence[TrackTemplate],
    action: TrackTemplateResultListener,
    strict: bool = False,
    log_fn: Callable[[int, str], None] | None = None,
    has_super_template: bool = False,
) -> TrackTemplateResultInfo:
    """Add a listener that fires when the result of a template changes.

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
    track_templates
        An iterable of TrackTemplate.
    action
        Callable to call with results.
    strict
        When set to True, raise on undefined variables.
    log_fn
        If not None, template error messages will logging by calling log_fn
        instead of the normal logging facility.
    has_super_template
        When set to True, the first template will block rendering of other
        templates if it doesn't render as True.

    Returns
    -------
    Info object used to unregister the listener, and refresh the template.

    """
    tracker = TrackTemplateResultInfo(hass, track_templates, action, has_super_template)
    tracker.async_setup(strict=strict, log_fn=log_fn)
    return tracker


@callback
@bind_hass
def async_track_same_state(
    hass: HomeAssistant,
    period: timedelta,
    action: Callable[[], Coroutine[Any, Any, None] | None],
    async_check_same_func: Callable[[str, State | None, State | None], bool],
    entity_ids: str | Iterable[str] = MATCH_ALL,
) -> CALLBACK_TYPE:
    """Track the state of entities for a period and run an action.

    If async_check_func is None it use the state of orig_value.
    Without entity_ids we track all state changes.
    """
    async_remove_state_for_cancel: CALLBACK_TYPE | None = None
    async_remove_state_for_listener: CALLBACK_TYPE | None = None

    job = HassJob(action, f"track same state {period} {entity_ids}")

    @callback
    def clear_listener() -> None:
        """Clear all unsub listener."""
        nonlocal async_remove_state_for_cancel, async_remove_state_for_listener

        if async_remove_state_for_listener is not None:
            async_remove_state_for_listener()
            async_remove_state_for_listener = None
        if async_remove_state_for_cancel is not None:
            async_remove_state_for_cancel()
            async_remove_state_for_cancel = None

    @callback
    def state_for_listener(now: Any) -> None:
        """Fire on state changes after a delay and calls action."""
        nonlocal async_remove_state_for_listener
        async_remove_state_for_listener = None
        clear_listener()
        hass.async_run_hass_job(job)

    @callback
    def state_for_cancel_listener(event: Event[EventStateChangedData]) -> None:
        """Fire on changes and cancel for listener if changed."""
        entity = event.data["entity_id"]
        from_state = event.data["old_state"]
        to_state = event.data["new_state"]

        if not async_check_same_func(entity, from_state, to_state):
            clear_listener()

    async_remove_state_for_listener = async_call_later(hass, period, state_for_listener)

    if entity_ids == MATCH_ALL:
        async_remove_state_for_cancel = hass.bus.async_listen(
            EVENT_STATE_CHANGED, state_for_cancel_listener
        )
    else:
        async_remove_state_for_cancel = async_track_state_change_event(
            hass,
            entity_ids,
            state_for_cancel_listener,
        )

    return clear_listener


track_same_state = threaded_listener_factory(async_track_same_state)


@callback
@bind_hass
def async_track_point_in_time(
    hass: HomeAssistant,
    action: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    | Callable[[datetime], Coroutine[Any, Any, None] | None],
    point_in_time: datetime,
) -> CALLBACK_TYPE:
    """Add a listener that fires once at or after a specific point in time.

    The listener is passed the time it fires in local time.
    """
    job = (
        action
        if isinstance(action, HassJob)
        else HassJob(action, f"track point in time {point_in_time}")
    )

    @callback
    def utc_converter(utc_now: datetime) -> None:
        """Convert passed in UTC now to local now."""
        hass.async_run_hass_job(job, dt_util.as_local(utc_now))

    track_job = HassJob(
        utc_converter,
        name=f"{job.name} UTC converter",
        cancel_on_shutdown=job.cancel_on_shutdown,
        job_type=HassJobType.Callback,
    )
    return async_track_point_in_utc_time(hass, track_job, point_in_time)


track_point_in_time = threaded_listener_factory(async_track_point_in_time)


@dataclass(slots=True)
class _TrackPointUTCTime:
    hass: HomeAssistant
    job: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    utc_point_in_time: datetime
    expected_fire_timestamp: float
    _cancel_callback: asyncio.TimerHandle | None = None

    def async_attach(self) -> None:
        """Initialize track job."""
        loop = self.hass.loop
        self._cancel_callback = loop.call_at(
            loop.time() + self.expected_fire_timestamp - time.time(), self
        )

    @callback
    def __call__(self) -> None:
        """Call the action.

        We implement this as __call__ so when debug logging logs the object
        it shows the name of the job. This is especially helpful when asyncio
        debug logging is enabled as we can see the name of the job that is
        being called that is blocking the event loop.
        """
        # Depending on the available clock support (including timer hardware
        # and the OS kernel) it can happen that we fire a little bit too early
        # as measured by utcnow(). That is bad when callbacks have assumptions
        # about the current time. Thus, we rearm the timer for the remaining
        # time.
        if (delta := (self.expected_fire_timestamp - time_tracker_timestamp())) > 0:
            _LOGGER.debug("Called %f seconds too early, rearming", delta)
            loop = self.hass.loop
            self._cancel_callback = loop.call_at(loop.time() + delta, self)
            return

        self.hass.async_run_hass_job(self.job, self.utc_point_in_time)

    @callback
    def async_cancel(self) -> None:
        """Cancel the call_at."""
        if TYPE_CHECKING:
            assert self._cancel_callback is not None
        self._cancel_callback.cancel()


@callback
@bind_hass
def async_track_point_in_utc_time(
    hass: HomeAssistant,
    action: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    | Callable[[datetime], Coroutine[Any, Any, None] | None],
    point_in_time: datetime,
) -> CALLBACK_TYPE:
    """Add a listener that fires once at or after a specific point in time.

    The listener is passed the time it fires in UTC time.
    """
    # Ensure point_in_time is UTC
    utc_point_in_time = dt_util.as_utc(point_in_time)
    expected_fire_timestamp = utc_point_in_time.timestamp()
    job = (
        action
        if isinstance(action, HassJob)
        else HassJob(action, f"track point in utc time {utc_point_in_time}")
    )
    track = _TrackPointUTCTime(hass, job, utc_point_in_time, expected_fire_timestamp)
    track.async_attach()
    return track.async_cancel


track_point_in_utc_time = threaded_listener_factory(async_track_point_in_utc_time)


def _run_async_call_action(
    hass: HomeAssistant, job: HassJob[[datetime], Coroutine[Any, Any, None] | None]
) -> None:
    """Run action."""
    hass.async_run_hass_job(job, time_tracker_utcnow())


@callback
@bind_hass
def async_call_at(
    hass: HomeAssistant,
    action: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    | Callable[[datetime], Coroutine[Any, Any, None] | None],
    loop_time: float,
) -> CALLBACK_TYPE:
    """Add a listener that fires at or after <loop_time>.

    The listener is passed the time it fires in UTC time.
    """
    job = (
        action
        if isinstance(action, HassJob)
        else HassJob(action, f"call_at {loop_time}")
    )
    return hass.loop.call_at(loop_time, _run_async_call_action, hass, job).cancel


@callback
@bind_hass
def async_call_later(
    hass: HomeAssistant,
    delay: float | timedelta,
    action: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    | Callable[[datetime], Coroutine[Any, Any, None] | None],
) -> CALLBACK_TYPE:
    """Add a listener that fires at or after <delay>.

    The listener is passed the time it fires in UTC time.
    """
    if isinstance(delay, timedelta):
        delay = delay.total_seconds()
    job = (
        action
        if isinstance(action, HassJob)
        else HassJob(action, f"call_later {delay}")
    )
    loop = hass.loop
    return loop.call_at(loop.time() + delay, _run_async_call_action, hass, job).cancel


call_later = threaded_listener_factory(async_call_later)


@dataclass(slots=True)
class _TrackTimeInterval:
    """Helper class to help listen to time interval events."""

    hass: HomeAssistant
    seconds: float
    job_name: str
    action: Callable[[datetime], Coroutine[Any, Any, None] | None]
    cancel_on_shutdown: bool | None
    _track_job: HassJob[[datetime], Coroutine[Any, Any, None] | None] | None = None
    _run_job: HassJob[[datetime], Coroutine[Any, Any, None] | None] | None = None
    _timer_handle: asyncio.TimerHandle | None = None

    def async_attach(self) -> None:
        """Initialize track job."""
        self._track_job = HassJob(
            self._interval_listener,
            self.job_name,
            job_type=HassJobType.Callback,
            cancel_on_shutdown=self.cancel_on_shutdown,
        )
        self._run_job = HassJob(
            self.action,
            f"track time interval {self.seconds}",
            cancel_on_shutdown=self.cancel_on_shutdown,
        )
        self._schedule_timer()

    def _schedule_timer(self) -> None:
        """Schedule the timer."""
        if TYPE_CHECKING:
            assert self._track_job is not None
        hass = self.hass
        loop = hass.loop
        self._timer_handle = loop.call_at(
            loop.time() + self.seconds, self._interval_listener, self._track_job
        )

    @callback
    def _interval_listener(self, _: Any) -> None:
        """Handle elapsed intervals."""
        if TYPE_CHECKING:
            assert self._run_job is not None
        self._schedule_timer()
        self.hass.async_run_hass_job(self._run_job, dt_util.utcnow(), background=True)

    @callback
    def async_cancel(self) -> None:
        """Cancel the call_at."""
        if TYPE_CHECKING:
            assert self._timer_handle is not None
        self._timer_handle.cancel()


@callback
@bind_hass
def async_track_time_interval(
    hass: HomeAssistant,
    action: Callable[[datetime], Coroutine[Any, Any, None] | None],
    interval: timedelta,
    *,
    name: str | None = None,
    cancel_on_shutdown: bool | None = None,
) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively at every timedelta interval.

    The listener is passed the time it fires in UTC time.
    """
    seconds = interval.total_seconds()
    job_name = f"track time interval {seconds} {action}"
    if name:
        job_name = f"{name}: {job_name}"
    track = _TrackTimeInterval(hass, seconds, job_name, action, cancel_on_shutdown)
    track.async_attach()
    return track.async_cancel


track_time_interval = threaded_listener_factory(async_track_time_interval)


@dataclass(slots=True)
class SunListener:
    """Helper class to help listen to sun events."""

    hass: HomeAssistant
    job: HassJob[[], Coroutine[Any, Any, None] | None]
    event: str
    offset: timedelta | None
    _unsub_sun: CALLBACK_TYPE | None = None
    _unsub_config: CALLBACK_TYPE | None = None

    @callback
    def async_attach(self) -> None:
        """Attach a sun listener."""
        assert self._unsub_config is None

        self._unsub_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._handle_config_event
        )

        self._listen_next_sun_event()

    @callback
    def async_detach(self) -> None:
        """Detach the sun listener."""
        assert self._unsub_sun is not None
        assert self._unsub_config is not None

        self._unsub_sun()
        self._unsub_sun = None
        self._unsub_config()
        self._unsub_config = None

    @callback
    def _listen_next_sun_event(self) -> None:
        """Set up the sun event listener."""
        assert self._unsub_sun is None

        self._unsub_sun = async_track_point_in_utc_time(
            self.hass,
            self._handle_sun_event,
            get_astral_event_next(self.hass, self.event, offset=self.offset),
        )

    @callback
    def _handle_sun_event(self, _now: Any) -> None:
        """Handle solar event."""
        self._unsub_sun = None
        self._listen_next_sun_event()
        self.hass.async_run_hass_job(self.job, background=True)

    @callback
    def _handle_config_event(self, _event: Any) -> None:
        """Handle core config update."""
        assert self._unsub_sun is not None
        self._unsub_sun()
        self._unsub_sun = None
        self._listen_next_sun_event()


@callback
@bind_hass
def async_track_sunrise(
    hass: HomeAssistant, action: Callable[[], None], offset: timedelta | None = None
) -> CALLBACK_TYPE:
    """Add a listener that will fire a specified offset from sunrise daily."""
    listener = SunListener(
        hass, HassJob(action, "track sunrise"), SUN_EVENT_SUNRISE, offset
    )
    listener.async_attach()
    return listener.async_detach


track_sunrise = threaded_listener_factory(async_track_sunrise)


@callback
@bind_hass
def async_track_sunset(
    hass: HomeAssistant, action: Callable[[], None], offset: timedelta | None = None
) -> CALLBACK_TYPE:
    """Add a listener that will fire a specified offset from sunset daily."""
    listener = SunListener(
        hass, HassJob(action, "track sunset"), SUN_EVENT_SUNSET, offset
    )
    listener.async_attach()
    return listener.async_detach


track_sunset = threaded_listener_factory(async_track_sunset)

# For targeted patching in tests
time_tracker_utcnow = dt_util.utcnow
time_tracker_timestamp = time.time


@dataclass(slots=True)
class _TrackUTCTimeChange:
    hass: HomeAssistant
    time_match_expression: tuple[list[int], list[int], list[int]]
    microsecond: int
    local: bool
    job: HassJob[[datetime], Coroutine[Any, Any, None] | None]
    listener_job_name: str
    _pattern_time_change_listener_job: HassJob[[datetime], None] | None = None
    _cancel_callback: CALLBACK_TYPE | None = None

    def async_attach(self) -> None:
        """Initialize track job."""
        self._pattern_time_change_listener_job = HassJob(
            self._pattern_time_change_listener,
            self.listener_job_name,
            job_type=HassJobType.Callback,
        )
        self._cancel_callback = async_track_point_in_utc_time(
            self.hass,
            self._pattern_time_change_listener_job,
            self._calculate_next(dt_util.utcnow()),
        )

    def _calculate_next(self, utc_now: datetime) -> datetime:
        """Calculate and set the next time the trigger should fire."""
        localized_now = dt_util.as_local(utc_now) if self.local else utc_now
        return dt_util.find_next_time_expression_time(
            localized_now, *self.time_match_expression
        ).replace(microsecond=self.microsecond)

    @callback
    def _pattern_time_change_listener(self, _: datetime) -> None:
        """Listen for matching time_changed events."""
        hass = self.hass
        # Fetch time again because we want the actual time, not the
        # time when the timer was scheduled
        utc_now = time_tracker_utcnow()
        localized_now = dt_util.as_local(utc_now) if self.local else utc_now
        if TYPE_CHECKING:
            assert self._pattern_time_change_listener_job is not None
        self._cancel_callback = async_track_point_in_utc_time(
            hass,
            self._pattern_time_change_listener_job,
            self._calculate_next(utc_now + timedelta(seconds=1)),
        )
        hass.async_run_hass_job(self.job, localized_now, background=True)

    @callback
    def async_cancel(self) -> None:
        """Cancel the call_at."""
        if TYPE_CHECKING:
            assert self._cancel_callback is not None
        self._cancel_callback()


@callback
@bind_hass
def async_track_utc_time_change(
    hass: HomeAssistant,
    action: Callable[[datetime], Coroutine[Any, Any, None] | None],
    hour: Any | None = None,
    minute: Any | None = None,
    second: Any | None = None,
    local: bool = False,
) -> CALLBACK_TYPE:
    """Add a listener that will fire every time the UTC or local time matches a pattern.

    The listener is passed the time it fires in UTC or local time.
    """
    # We do not have to wrap the function with time pattern matching logic
    # if no pattern given
    if all(val is None or val == "*" for val in (hour, minute, second)):
        # Previously this relied on EVENT_TIME_FIRED
        # which meant it would not fire right away because
        # the caller would always be misaligned with the call
        # time vs the fire time by < 1s. To preserve this
        # misalignment we use async_track_time_interval here
        return async_track_time_interval(hass, action, timedelta(seconds=1))

    job = HassJob(action, f"track time change {hour}:{minute}:{second} local={local}")
    matching_seconds = dt_util.parse_time_expression(second, 0, 59)
    matching_minutes = dt_util.parse_time_expression(minute, 0, 59)
    matching_hours = dt_util.parse_time_expression(hour, 0, 23)
    # Avoid aligning all time trackers to the same fraction of a second
    # since it can create a thundering herd problem
    # https://github.com/home-assistant/core/issues/82231
    microsecond = randint(RANDOM_MICROSECOND_MIN, RANDOM_MICROSECOND_MAX)
    listener_job_name = f"time change listener {hour}:{minute}:{second} {action}"
    track = _TrackUTCTimeChange(
        hass,
        (matching_seconds, matching_minutes, matching_hours),
        microsecond,
        local,
        job,
        listener_job_name,
    )
    track.async_attach()
    return track.async_cancel


track_utc_time_change = threaded_listener_factory(async_track_utc_time_change)


@callback
@bind_hass
def async_track_time_change(
    hass: HomeAssistant,
    action: Callable[[datetime], Coroutine[Any, Any, None] | None],
    hour: Any | None = None,
    minute: Any | None = None,
    second: Any | None = None,
) -> CALLBACK_TYPE:
    """Add a listener that will fire every time the local time matches a pattern.

    The listener is passed the time it fires in local time.
    """
    return async_track_utc_time_change(hass, action, hour, minute, second, local=True)


track_time_change = threaded_listener_factory(async_track_time_change)


def process_state_match(
    parameter: str | Iterable[str] | None, invert: bool = False
) -> Callable[[str | None], bool]:
    """Convert parameter to function that matches input against parameter."""
    if parameter is None or parameter == MATCH_ALL:
        return lambda _: not invert

    if isinstance(parameter, str) or not hasattr(parameter, "__iter__"):
        return lambda state: invert is not (state == parameter)

    parameter_set = set(parameter)
    return lambda state: invert is not (state in parameter_set)


@callback
def _entities_domains_from_render_infos(
    render_infos: Iterable[RenderInfo],
) -> tuple[set[str], set[str]]:
    """Combine from multiple RenderInfo."""
    entities: set[str] = set()
    domains: set[str] = set()

    for render_info in render_infos:
        if render_info.entities:
            entities.update(render_info.entities)
        if render_info.domains:
            domains.update(render_info.domains)
        if render_info.domains_lifecycle:
            domains.update(render_info.domains_lifecycle)
    return entities, domains


@callback
def _render_infos_needs_all_listener(render_infos: Iterable[RenderInfo]) -> bool:
    """Determine if an all listener is needed from RenderInfo."""
    for render_info in render_infos:
        # Tracking all states
        if render_info.all_states or render_info.all_states_lifecycle:
            return True

    return False


@callback
def _render_infos_to_track_states(render_infos: Iterable[RenderInfo]) -> TrackStates:
    """Create a TrackStates dataclass from the latest RenderInfo."""
    if _render_infos_needs_all_listener(render_infos):
        return TrackStates(True, set(), set())

    return TrackStates(False, *_entities_domains_from_render_infos(render_infos))


@callback
def _event_triggers_rerender(
    event: Event[EventStateChangedData], info: RenderInfo
) -> bool:
    """Determine if a template should be re-rendered from an event."""
    entity_id = event.data["entity_id"]

    if info.filter(entity_id):
        return True

    if event.data["new_state"] is not None and event.data["old_state"] is not None:
        return False

    return bool(info.filter_lifecycle(entity_id))


@callback
def _rate_limit_for_event(
    event: Event[EventStateChangedData],
    info: RenderInfo,
    track_template_: TrackTemplate,
) -> float | None:
    """Determine the rate limit for an event."""
    # Specifically referenced entities are excluded
    # from the rate limit
    if event.data["entity_id"] in info.entities:
        return None

    if track_template_.rate_limit is not None:
        return track_template_.rate_limit

    rate_limit: float | None = info.rate_limit
    return rate_limit


def _suppress_domain_all_in_render_info(render_info: RenderInfo) -> RenderInfo:
    """Remove the domains and all_states from render info during a ratelimit."""
    rate_limited_render_info = copy.copy(render_info)
    rate_limited_render_info.all_states = False
    rate_limited_render_info.all_states_lifecycle = False
    rate_limited_render_info.domains = set()
    rate_limited_render_info.domains_lifecycle = set()
    return rate_limited_render_info
