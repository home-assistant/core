"""Helpers for listening to events."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import functools as ft
import logging
import time
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

import attr

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NOW,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
    MATCH_ALL,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.helpers.template import RenderInfo, Template, result_as_boolean
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe

MAX_TIME_TRACKING_ERROR = 0.001

TRACK_STATE_CHANGE_CALLBACKS = "track_state_change_callbacks"
TRACK_STATE_CHANGE_LISTENER = "track_state_change_listener"

TRACK_STATE_ADDED_DOMAIN_CALLBACKS = "track_state_added_domain_callbacks"
TRACK_STATE_ADDED_DOMAIN_LISTENER = "track_state_added_domain_listener"

TRACK_ENTITY_REGISTRY_UPDATED_CALLBACKS = "track_entity_registry_updated_callbacks"
TRACK_ENTITY_REGISTRY_UPDATED_LISTENER = "track_entity_registry_updated_listener"

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrackTemplate:
    """Class for keeping track of a template with variables.

    The template is template to calculate.
    The variables are variables to pass to the template.
    """

    template: Template
    variables: TemplateVarsType


@dataclass
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
    last_result: Union[str, None, TemplateError]
    result: Union[str, TemplateError]


def threaded_listener_factory(async_factory: Callable[..., Any]) -> CALLBACK_TYPE:
    """Convert an async event helper to a threaded one."""

    @ft.wraps(async_factory)
    def factory(*args: Any, **kwargs: Any) -> CALLBACK_TYPE:
        """Call async event helper safely."""
        hass = args[0]

        if not isinstance(hass, HomeAssistant):
            raise TypeError("First parameter needs to be a hass instance")

        async_remove = run_callback_threadsafe(
            hass.loop, ft.partial(async_factory, *args, **kwargs)
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
    entity_ids: Union[str, Iterable[str]],
    action: Callable[[str, State, State], None],
    from_state: Union[None, str, Iterable[str]] = None,
    to_state: Union[None, str, Iterable[str]] = None,
) -> CALLBACK_TYPE:
    """Track specific state changes.

    entity_ids, from_state and to_state can be string or list.
    Use list to match multiple.

    Returns a function that can be called to remove the listener.

    If entity_ids are not MATCH_ALL along with from_state and to_state
    being None, async_track_state_change_event should be used instead
    as it is slightly faster.

    Must be run within the event loop.
    """
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

    @callback
    def state_change_listener(event: Event) -> None:
        """Handle specific state changes."""
        if from_state is not None:
            old_state = event.data.get("old_state")
            if old_state is not None:
                old_state = old_state.state

            if not match_from_state(old_state):
                return
        if to_state is not None:
            new_state = event.data.get("new_state")
            if new_state is not None:
                new_state = new_state.state

            if not match_to_state(new_state):
                return

        hass.async_run_job(
            action,
            event.data.get("entity_id"),
            event.data.get("old_state"),
            event.data.get("new_state"),
        )

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

    return hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)


track_state_change = threaded_listener_factory(async_track_state_change)


@bind_hass
def async_track_state_change_event(
    hass: HomeAssistant,
    entity_ids: Union[str, Iterable[str]],
    action: Callable[[Event], Any],
) -> Callable[[], None]:
    """Track specific state change events indexed by entity_id.

    Unlike async_track_state_change, async_track_state_change_event
    passes the full event to the callback.

    In order to avoid having to iterate a long list
    of EVENT_STATE_CHANGED and fire and create a job
    for each one, we keep a dict of entity ids that
    care about the state change events so we can
    do a fast dict lookup to route events.
    """

    entity_callbacks = hass.data.setdefault(TRACK_STATE_CHANGE_CALLBACKS, {})

    if TRACK_STATE_CHANGE_LISTENER not in hass.data:

        @callback
        def _async_state_change_dispatcher(event: Event) -> None:
            """Dispatch state changes by entity_id."""
            entity_id = event.data.get("entity_id")

            if entity_id not in entity_callbacks:
                return

            for action in entity_callbacks[entity_id][:]:
                try:
                    hass.async_run_job(action, event)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception(
                        "Error while processing state changed for %s", entity_id
                    )

        hass.data[TRACK_STATE_CHANGE_LISTENER] = hass.bus.async_listen(
            EVENT_STATE_CHANGED, _async_state_change_dispatcher
        )

    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    entity_ids = [entity_id.lower() for entity_id in entity_ids]

    for entity_id in entity_ids:
        entity_callbacks.setdefault(entity_id, []).append(action)

    @callback
    def remove_listener() -> None:
        """Remove state change listener."""
        _async_remove_indexed_listeners(
            hass,
            TRACK_STATE_CHANGE_CALLBACKS,
            TRACK_STATE_CHANGE_LISTENER,
            entity_ids,
            action,
        )

    return remove_listener


@callback
def _async_remove_indexed_listeners(
    hass: HomeAssistant,
    data_key: str,
    listener_key: str,
    storage_keys: Iterable[str],
    action: Callable[[Event], Any],
) -> None:
    """Remove a listener."""

    callbacks = hass.data[data_key]

    for storage_key in storage_keys:
        callbacks[storage_key].remove(action)
        if len(callbacks[storage_key]) == 0:
            del callbacks[storage_key]

    if not callbacks:
        hass.data[listener_key]()
        del hass.data[listener_key]


@bind_hass
def async_track_entity_registry_updated_event(
    hass: HomeAssistant,
    entity_ids: Union[str, Iterable[str]],
    action: Callable[[Event], Any],
) -> Callable[[], None]:
    """Track specific entity registry updated events indexed by entity_id.

    Similar to async_track_state_change_event.
    """

    entity_callbacks = hass.data.setdefault(TRACK_ENTITY_REGISTRY_UPDATED_CALLBACKS, {})

    if TRACK_ENTITY_REGISTRY_UPDATED_LISTENER not in hass.data:

        @callback
        def _async_entity_registry_updated_dispatcher(event: Event) -> None:
            """Dispatch entity registry updates by entity_id."""
            entity_id = event.data.get("old_entity_id", event.data["entity_id"])

            if entity_id not in entity_callbacks:
                return

            for action in entity_callbacks[entity_id][:]:
                try:
                    hass.async_run_job(action, event)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception(
                        "Error while processing entity registry update for %s",
                        entity_id,
                    )

        hass.data[TRACK_ENTITY_REGISTRY_UPDATED_LISTENER] = hass.bus.async_listen(
            EVENT_ENTITY_REGISTRY_UPDATED, _async_entity_registry_updated_dispatcher
        )

    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    entity_ids = [entity_id.lower() for entity_id in entity_ids]

    for entity_id in entity_ids:
        entity_callbacks.setdefault(entity_id, []).append(action)

    @callback
    def remove_listener() -> None:
        """Remove state change listener."""
        _async_remove_indexed_listeners(
            hass,
            TRACK_ENTITY_REGISTRY_UPDATED_CALLBACKS,
            TRACK_ENTITY_REGISTRY_UPDATED_LISTENER,
            entity_ids,
            action,
        )

    return remove_listener


@bind_hass
def async_track_state_added_domain(
    hass: HomeAssistant,
    domains: Union[str, Iterable[str]],
    action: Callable[[Event], Any],
) -> Callable[[], None]:
    """Track state change events when an entity is added to domains."""

    domain_callbacks = hass.data.setdefault(TRACK_STATE_ADDED_DOMAIN_CALLBACKS, {})

    if TRACK_STATE_ADDED_DOMAIN_LISTENER not in hass.data:

        @callback
        def _async_state_change_dispatcher(event: Event) -> None:
            """Dispatch state changes by entity_id."""
            if event.data.get("old_state") is not None:
                return

            domain = split_entity_id(event.data["entity_id"])[0]

            if domain not in domain_callbacks:
                return

            for action in domain_callbacks[domain][:]:
                try:
                    hass.async_run_job(action, event)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception(
                        "Error while processing state added for %s", domain
                    )

        hass.data[TRACK_STATE_ADDED_DOMAIN_LISTENER] = hass.bus.async_listen(
            EVENT_STATE_CHANGED, _async_state_change_dispatcher
        )

    if isinstance(domains, str):
        domains = [domains]

    domains = [domains.lower() for domains in domains]

    for domain in domains:
        domain_callbacks.setdefault(domain, []).append(action)

    @callback
    def remove_listener() -> None:
        """Remove state change listener."""
        _async_remove_indexed_listeners(
            hass,
            TRACK_STATE_ADDED_DOMAIN_CALLBACKS,
            TRACK_STATE_ADDED_DOMAIN_LISTENER,
            domains,
            action,
        )

    return remove_listener


@callback
@bind_hass
def async_track_template(
    hass: HomeAssistant,
    template: Template,
    action: Callable[[str, Optional[State], Optional[State]], None],
    variables: Optional[TemplateVarsType] = None,
) -> Callable[[], None]:
    """Add a listener that fires when a a template evaluates to 'true'.

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

    @callback
    def _template_changed_listener(
        event: Event, updates: List[TrackTemplateResult]
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

        hass.async_run_job(
            action,
            event.data.get("entity_id"),
            event.data.get("old_state"),
            event.data.get("new_state"),
        )

    info = async_track_template_result(
        hass, [TrackTemplate(template, variables)], _template_changed_listener
    )

    return info.async_remove


track_template = threaded_listener_factory(async_track_template)


class _TrackTemplateResultInfo:
    """Handle removal / refresh of tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        track_templates: Iterable[TrackTemplate],
        action: Callable,
    ):
        """Handle removal / refresh of tracker init."""
        self.hass = hass
        self._action = action

        for track_template_ in track_templates:
            track_template_.template.hass = hass
        self._track_templates = track_templates

        self._all_listener: Optional[Callable] = None
        self._domains_listener: Optional[Callable] = None
        self._entities_listener: Optional[Callable] = None

        self._last_result: Dict[Template, Union[str, TemplateError]] = {}
        self._last_info: Dict[Template, RenderInfo] = {}
        self._info: Dict[Template, RenderInfo] = {}
        self._last_domains: Set = set()
        self._last_entities: Set = set()
        self._entity_ids_filter: Set = set()

    def async_setup(self) -> None:
        """Activation of template tracking."""
        for track_template_ in self._track_templates:
            template = track_template_.template
            variables = track_template_.variables

            self._info[template] = template.async_render_to_info(variables)
            if self._info[template].exception:
                _LOGGER.error(
                    "Error while processing template: %s",
                    track_template_.template,
                    exc_info=self._info[template].exception,
                )

        self._last_info = self._info.copy()
        self._create_listeners()

    @property
    def _needs_all_listener(self) -> bool:
        for track_template_ in self._track_templates:
            template = track_template_.template

            # Tracking all states
            if self._info[template].all_states:
                return True

            # Previous call had an exception
            # so we do not know which states
            # to track
            if self._info[template].exception:
                return True

        return False

    @property
    def _all_templates_are_static(self) -> bool:
        for track_template_ in self._track_templates:
            if not self._info[track_template_.template].is_static:
                return False

        return True

    @callback
    def _create_listeners(self) -> None:
        if self._all_templates_are_static:
            return

        if self._needs_all_listener:
            self._setup_all_listener()
            return

        self._last_entities, self._last_domains = _entities_domains_from_info(
            self._info.values()
        )
        self._setup_domains_listener(self._last_domains)
        self._setup_entities_listener(self._last_domains, self._last_entities)

    @callback
    def _cancel_domains_listener(self) -> None:
        if self._domains_listener is None:
            return
        self._domains_listener()
        self._domains_listener = None

    @callback
    def _cancel_entities_listener(self) -> None:
        if self._entities_listener is None:
            return
        self._entities_listener()
        self._entities_listener = None

    @callback
    def _cancel_all_listener(self) -> None:
        if self._all_listener is None:
            return
        self._all_listener()
        self._all_listener = None

    @callback
    def _update_listeners(self) -> None:
        if self._needs_all_listener:
            if self._all_listener:
                return
            self._last_domains = set()
            self._last_entities = set()
            self._cancel_domains_listener()
            self._cancel_entities_listener()
            self._setup_all_listener()
            return

        had_all_listener = self._all_listener is not None
        if had_all_listener:
            self._cancel_all_listener()

        entities, domains = _entities_domains_from_info(self._info.values())
        domains_changed = domains != self._last_domains

        if had_all_listener or domains_changed:
            domains_changed = True
            self._cancel_domains_listener()
            self._setup_domains_listener(domains)

        if had_all_listener or domains_changed or entities != self._last_entities:
            self._cancel_entities_listener()
            self._setup_entities_listener(domains, entities)

        self._last_domains = domains
        self._last_entities = entities

    @callback
    def _setup_entities_listener(self, domains: Set, entities: Set) -> None:
        if domains:
            entities = entities.copy()
            entities.update(self.hass.states.async_entity_ids(domains))

        # Entities has changed to none
        if not entities:
            return

        self._entities_listener = async_track_state_change_event(
            self.hass, entities, self._refresh
        )

    @callback
    def _setup_domains_listener(self, domains: Set) -> None:
        if not domains:
            return

        self._domains_listener = async_track_state_added_domain(
            self.hass, domains, self._refresh
        )

    @callback
    def _setup_all_listener(self) -> None:
        self._all_listener = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._refresh
        )

    @callback
    def async_remove(self) -> None:
        """Cancel the listener."""
        self._cancel_all_listener()
        self._cancel_domains_listener()
        self._cancel_entities_listener()

    @callback
    def async_refresh(self) -> None:
        """Force recalculate the template."""
        self._refresh(None)

    @callback
    def async_update_entity_ids_filter(self, entity_ids: Set) -> None:
        """Update the filtered entity_ids."""
        self._entity_ids_filter = entity_ids

    @callback
    def _refresh(self, event: Optional[Event]) -> None:
        entity_id = event and event.data.get(ATTR_ENTITY_ID)
        updates = []
        info_changed = False

        if entity_id and entity_id in self._entity_ids_filter:
            # Skip self-referencing updates
            for track_template_ in self._track_templates:
                _LOGGER.warning(
                    "Template loop detected while processing event: %s, skipping template render for Template[%s]",
                    event,
                    track_template_.template.template,
                )
            return

        for track_template_ in self._track_templates:
            template = track_template_.template
            if (
                entity_id
                and len(self._last_info) > 1
                and not self._last_info[template].filter_lifecycle(entity_id)
            ):
                continue

            self._info[template] = template.async_render_to_info(
                track_template_.variables
            )
            info_changed = True

            try:
                result: Union[str, TemplateError] = self._info[template].result()
            except TemplateError as ex:
                result = ex

            last_result = self._last_result.get(template)

            # Check to see if the result has changed
            if result == last_result:
                continue

            if isinstance(result, TemplateError) and isinstance(
                last_result, TemplateError
            ):
                continue

            updates.append(TrackTemplateResult(template, last_result, result))

        if info_changed:
            self._update_listeners()
            self._last_info = self._info.copy()

        if not updates:
            return

        for track_result in updates:
            self._last_result[track_result.template] = track_result.result

        self.hass.async_run_job(self._action, event, updates)


TrackTemplateResultListener = Callable[
    [
        Event,
        List[TrackTemplateResult],
    ],
    None,
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
    track_templates: Iterable[TrackTemplate],
    action: TrackTemplateResultListener,
) -> _TrackTemplateResultInfo:
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
    track_templates
        An iterable of TrackTemplate.

    action
        Callable to call with results.

    Returns
    -------
    Info object used to unregister the listener, and refresh the template.

    """
    tracker = _TrackTemplateResultInfo(hass, track_templates, action)
    tracker.async_setup()
    return tracker


@callback
@bind_hass
def async_track_same_state(
    hass: HomeAssistant,
    period: timedelta,
    action: Callable[..., None],
    async_check_same_func: Callable[[str, Optional[State], Optional[State]], bool],
    entity_ids: Union[str, Iterable[str]] = MATCH_ALL,
) -> CALLBACK_TYPE:
    """Track the state of entities for a period and run an action.

    If async_check_func is None it use the state of orig_value.
    Without entity_ids we track all state changes.
    """
    async_remove_state_for_cancel: Optional[CALLBACK_TYPE] = None
    async_remove_state_for_listener: Optional[CALLBACK_TYPE] = None

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
        hass.async_run_job(action)

    @callback
    def state_for_cancel_listener(event: Event) -> None:
        """Fire on changes and cancel for listener if changed."""
        entity: str = event.data["entity_id"]
        from_state: Optional[State] = event.data.get("old_state")
        to_state: Optional[State] = event.data.get("new_state")

        if not async_check_same_func(entity, from_state, to_state):
            clear_listener()

    async_remove_state_for_listener = async_track_point_in_utc_time(
        hass, state_for_listener, dt_util.utcnow() + period
    )

    if entity_ids == MATCH_ALL:
        async_remove_state_for_cancel = hass.bus.async_listen(
            EVENT_STATE_CHANGED, state_for_cancel_listener
        )
    else:
        async_remove_state_for_cancel = async_track_state_change_event(
            hass,
            [entity_ids] if isinstance(entity_ids, str) else entity_ids,
            state_for_cancel_listener,
        )

    return clear_listener


track_same_state = threaded_listener_factory(async_track_same_state)


@callback
@bind_hass
def async_track_point_in_time(
    hass: HomeAssistant, action: Callable[..., None], point_in_time: datetime
) -> CALLBACK_TYPE:
    """Add a listener that fires once after a specific point in time."""

    @callback
    def utc_converter(utc_now: datetime) -> None:
        """Convert passed in UTC now to local now."""
        hass.async_run_job(action, dt_util.as_local(utc_now))

    return async_track_point_in_utc_time(hass, utc_converter, point_in_time)


track_point_in_time = threaded_listener_factory(async_track_point_in_time)


@callback
@bind_hass
def async_track_point_in_utc_time(
    hass: HomeAssistant, action: Callable[..., Any], point_in_time: datetime
) -> CALLBACK_TYPE:
    """Add a listener that fires once after a specific point in UTC time."""
    # Ensure point_in_time is UTC
    utc_point_in_time = dt_util.as_utc(point_in_time)

    cancel_callback = hass.loop.call_at(
        hass.loop.time() + point_in_time.timestamp() - time.time(),
        hass.async_run_job,
        action,
        utc_point_in_time,
    )

    @callback
    def unsub_point_in_time_listener() -> None:
        """Cancel the call_later."""
        cancel_callback.cancel()

    return unsub_point_in_time_listener


track_point_in_utc_time = threaded_listener_factory(async_track_point_in_utc_time)


@callback
@bind_hass
def async_call_later(
    hass: HomeAssistant, delay: float, action: Callable[..., None]
) -> CALLBACK_TYPE:
    """Add a listener that is called in <delay>."""
    return async_track_point_in_utc_time(
        hass, action, dt_util.utcnow() + timedelta(seconds=delay)
    )


call_later = threaded_listener_factory(async_call_later)


@callback
@bind_hass
def async_track_time_interval(
    hass: HomeAssistant,
    action: Callable[..., Union[None, Awaitable]],
    interval: timedelta,
) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively at every timedelta interval."""
    remove = None

    def next_interval() -> datetime:
        """Return the next interval."""
        return dt_util.utcnow() + interval

    @callback
    def interval_listener(now: datetime) -> None:
        """Handle elapsed intervals."""
        nonlocal remove
        remove = async_track_point_in_utc_time(hass, interval_listener, next_interval())
        hass.async_run_job(action, now)

    remove = async_track_point_in_utc_time(hass, interval_listener, next_interval())

    def remove_listener() -> None:
        """Remove interval listener."""
        remove()

    return remove_listener


track_time_interval = threaded_listener_factory(async_track_time_interval)


@attr.s
class SunListener:
    """Helper class to help listen to sun events."""

    hass: HomeAssistant = attr.ib()
    action: Callable[..., None] = attr.ib()
    event: str = attr.ib()
    offset: Optional[timedelta] = attr.ib()
    _unsub_sun: Optional[CALLBACK_TYPE] = attr.ib(default=None)
    _unsub_config: Optional[CALLBACK_TYPE] = attr.ib(default=None)

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
        self.hass.async_run_job(self.action)

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
    hass: HomeAssistant, action: Callable[..., None], offset: Optional[timedelta] = None
) -> CALLBACK_TYPE:
    """Add a listener that will fire a specified offset from sunrise daily."""
    listener = SunListener(hass, action, SUN_EVENT_SUNRISE, offset)
    listener.async_attach()
    return listener.async_detach


track_sunrise = threaded_listener_factory(async_track_sunrise)


@callback
@bind_hass
def async_track_sunset(
    hass: HomeAssistant, action: Callable[..., None], offset: Optional[timedelta] = None
) -> CALLBACK_TYPE:
    """Add a listener that will fire a specified offset from sunset daily."""
    listener = SunListener(hass, action, SUN_EVENT_SUNSET, offset)
    listener.async_attach()
    return listener.async_detach


track_sunset = threaded_listener_factory(async_track_sunset)

# For targeted patching in tests
pattern_utc_now = dt_util.utcnow


@callback
@bind_hass
def async_track_utc_time_change(
    hass: HomeAssistant,
    action: Callable[..., None],
    hour: Optional[Any] = None,
    minute: Optional[Any] = None,
    second: Optional[Any] = None,
    local: bool = False,
) -> CALLBACK_TYPE:
    """Add a listener that will fire if time matches a pattern."""
    # We do not have to wrap the function with time pattern matching logic
    # if no pattern given
    if all(val is None for val in (hour, minute, second)):

        @callback
        def time_change_listener(event: Event) -> None:
            """Fire every time event that comes in."""
            hass.async_run_job(action, event.data[ATTR_NOW])

        return hass.bus.async_listen(EVENT_TIME_CHANGED, time_change_listener)

    matching_seconds = dt_util.parse_time_expression(second, 0, 59)
    matching_minutes = dt_util.parse_time_expression(minute, 0, 59)
    matching_hours = dt_util.parse_time_expression(hour, 0, 23)

    next_time: datetime = dt_util.utcnow()

    def calculate_next(now: datetime) -> None:
        """Calculate and set the next time the trigger should fire."""
        nonlocal next_time

        localized_now = dt_util.as_local(now) if local else now
        next_time = dt_util.find_next_time_expression_time(
            localized_now, matching_seconds, matching_minutes, matching_hours
        )

    # Make sure rolling back the clock doesn't prevent the timer from
    # triggering.
    cancel_callback: Optional[asyncio.TimerHandle] = None
    calculate_next(next_time)

    @callback
    def pattern_time_change_listener() -> None:
        """Listen for matching time_changed events."""
        nonlocal next_time, cancel_callback

        now = pattern_utc_now()
        hass.async_run_job(action, dt_util.as_local(now) if local else now)

        calculate_next(now + timedelta(seconds=1))

        cancel_callback = hass.loop.call_at(
            -time.time()
            + hass.loop.time()
            + next_time.timestamp()
            + MAX_TIME_TRACKING_ERROR,
            pattern_time_change_listener,
        )

    # We always get time.time() first to avoid time.time()
    # ticking forward after fetching hass.loop.time()
    # and callback being scheduled a few microseconds early.
    #
    # Since we loose additional time calling `hass.loop.time()`
    # we add MAX_TIME_TRACKING_ERROR to ensure
    # we always schedule the call within the time window between
    # second and the next second.
    #
    # For example:
    # If the clock ticks forward 30 microseconds when fectching
    # `hass.loop.time()` and we want the event to fire at exactly
    # 03:00:00.000000, the event would actually fire around
    # 02:59:59.999970. To ensure we always fire sometime between
    # 03:00:00.000000 and 03:00:00.999999 we add
    # MAX_TIME_TRACKING_ERROR to make up for the time
    # lost fetching the time. This ensures we do not fire the
    # event before the next time pattern match which would result
    # in the event being fired again since we would otherwise
    # potentially fire early.
    #
    cancel_callback = hass.loop.call_at(
        -time.time()
        + hass.loop.time()
        + next_time.timestamp()
        + MAX_TIME_TRACKING_ERROR,
        pattern_time_change_listener,
    )

    @callback
    def unsub_pattern_time_change_listener() -> None:
        """Cancel the call_later."""
        nonlocal cancel_callback
        assert cancel_callback is not None
        cancel_callback.cancel()

    return unsub_pattern_time_change_listener


track_utc_time_change = threaded_listener_factory(async_track_utc_time_change)


@callback
@bind_hass
def async_track_time_change(
    hass: HomeAssistant,
    action: Callable[..., None],
    hour: Optional[Any] = None,
    minute: Optional[Any] = None,
    second: Optional[Any] = None,
) -> CALLBACK_TYPE:
    """Add a listener that will fire if UTC time matches a pattern."""
    return async_track_utc_time_change(hass, action, hour, minute, second, local=True)


track_time_change = threaded_listener_factory(async_track_time_change)


def process_state_match(
    parameter: Union[None, str, Iterable[str]]
) -> Callable[[str], bool]:
    """Convert parameter to function that matches input against parameter."""
    if parameter is None or parameter == MATCH_ALL:
        return lambda _: True

    if isinstance(parameter, str) or not hasattr(parameter, "__iter__"):
        return lambda state: state == parameter

    parameter_set = set(parameter)
    return lambda state: state in parameter_set


def _entities_domains_from_info(render_infos: Iterable[RenderInfo]) -> Tuple[Set, Set]:
    """Combine from multiple RenderInfo."""
    entities = set()
    domains = set()

    for render_info in render_infos:
        if render_info.entities:
            entities.update(render_info.entities)
        if render_info.domains:
            domains.update(render_info.domains)
    return entities, domains
