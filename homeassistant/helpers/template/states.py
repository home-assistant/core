"""State wrapper classes and helpers for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from datetime import datetime
from enum import Enum
from functools import cache, partial
from typing import Any

from lru import LRU
from propcache.api import under_cached_property

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import (
    Context,
    HomeAssistant,
    State,
    valid_domain,
    valid_entity_id,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import (
    async_translate_state,
    async_translate_state_attr,
)
from homeassistant.util.read_only_dict import ReadOnlyDict

from .render_info import render_info_cv

_SENTINEL = object()

_RESERVED_NAMES = {
    "contextfunction",
    "evalcontextfunction",
    "environmentfunction",
    "jinja_pass_arg",
}

_COLLECTABLE_STATE_ATTRIBUTES = {
    "state",
    "attributes",
    "last_changed",
    "last_updated",
    "context",
    "domain",
    "object_id",
    "name",
}


#
# CACHED_TEMPLATE_STATES is a rough estimate of the number of entities
# on a typical system. It is used as the initial size of the LRU cache
# for TemplateState objects.
#
# If the cache is too small we will end up creating and destroying
# TemplateState objects too often which will cause a lot of GC activity
# and slow down the system. For systems with a lot of entities and
# templates, this can reach 100000s of object creations and destructions
# per minute.
#
# Since entity counts may grow over time, we will increase
# the size if the number of entities grows via _async_adjust_lru_sizes
# at the start of the system and every 10 minutes if needed.
#
CACHED_TEMPLATE_STATES = 512

CACHED_TEMPLATE_LRU: LRU[State, TemplateState] = LRU(CACHED_TEMPLATE_STATES)
CACHED_TEMPLATE_NO_COLLECT_LRU: LRU[State, TemplateState] = LRU(CACHED_TEMPLATE_STATES)
ENTITY_COUNT_GROWTH_FACTOR = 1.2


def _template_state_no_collect(hass: HomeAssistant, state: State) -> TemplateState:
    """Return a TemplateState for a state without collecting."""
    if template_state := CACHED_TEMPLATE_NO_COLLECT_LRU.get(state):
        return template_state
    template_state = _create_template_state_no_collect(hass, state)
    CACHED_TEMPLATE_NO_COLLECT_LRU[state] = template_state
    return template_state


def _template_state(hass: HomeAssistant, state: State) -> TemplateState:
    """Return a TemplateState for a state that collects."""
    if template_state := CACHED_TEMPLATE_LRU.get(state):
        return template_state
    template_state = TemplateState(hass, state)
    CACHED_TEMPLATE_LRU[state] = template_state
    return template_state


@cache
def _domain_states(hass: HomeAssistant, name: str) -> DomainStates:
    return DomainStates(hass, name)


def _readonly(*args: Any, **kwargs: Any) -> Any:
    """Raise an exception when a states object is modified."""
    raise RuntimeError(f"Cannot modify template States object: {args} {kwargs}")


class AllStates:
    """Class to expose all HA states as attributes."""

    __setitem__ = _readonly
    __delitem__ = _readonly
    __slots__ = ("_hass",)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize all states."""
        self._hass = hass

    def __getattr__(self, name: str) -> Any:
        """Return the domain state."""
        if "." in name:
            return _get_state_if_valid(self._hass, name)

        if name in _RESERVED_NAMES:
            return None

        if not valid_domain(name):
            raise TemplateError(f"Invalid domain name '{name}'")

        return _domain_states(self._hass, name)

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    __getitem__ = __getattr__

    def _collect_all(self) -> None:
        if (render_info := render_info_cv.get()) is not None:
            render_info.all_states = True

    def _collect_all_lifecycle(self) -> None:
        if (render_info := render_info_cv.get()) is not None:
            render_info.all_states_lifecycle = True

    def __iter__(self) -> Generator[TemplateState]:
        """Return all states."""
        self._collect_all()
        return _state_generator(self._hass, None)

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_all_lifecycle()
        return self._hass.states.async_entity_ids_count()

    def __call__(
        self,
        entity_id: str,
        rounded: bool | object = _SENTINEL,
        with_unit: bool = False,
    ) -> str:
        """Return the states."""
        state = _get_state(self._hass, entity_id)
        if state is None:
            return STATE_UNKNOWN
        if rounded is _SENTINEL:
            rounded = with_unit
        if rounded or with_unit:
            return state.format_state(rounded, with_unit)  # type: ignore[arg-type]
        return state.state

    def __repr__(self) -> str:
        """Representation of All States."""
        return "<template AllStates>"


class StateTranslated:
    """Class to represent a translated state in a template."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize all states."""
        self._hass = hass

    def __call__(self, entity_id: str) -> str | None:
        """Retrieve translated state if available."""
        state = _get_state_if_valid(self._hass, entity_id)

        if state is None:
            return STATE_UNKNOWN

        state_value = state.state
        domain = state.domain
        device_class = state.attributes.get("device_class")
        entry = er.async_get(self._hass).async_get(entity_id)
        platform = None if entry is None else entry.platform
        translation_key = None if entry is None else entry.translation_key

        return async_translate_state(
            self._hass, state_value, domain, platform, translation_key, device_class
        )

    def __repr__(self) -> str:
        """Representation of Translated state."""
        return "<template StateTranslated>"


class StateAttrTranslated:
    """Class to represent a translated state attribute value in a template."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass

    def __call__(self, entity_id: str, attribute: str) -> Any:
        """Retrieve translated state attribute value if available."""
        state = _get_state_if_valid(self._hass, entity_id)

        if state is None:
            return None

        attr_value = state.attributes.get(attribute)
        if attr_value is None:
            return None

        if not isinstance(attr_value, str | Enum):
            return attr_value

        domain = state.domain
        device_class = state.attributes.get("device_class")
        entry = er.async_get(self._hass).async_get(entity_id)
        platform = None if entry is None else entry.platform
        translation_key = None if entry is None else entry.translation_key

        return async_translate_state_attr(
            self._hass,
            str(attr_value),
            domain,
            platform,
            translation_key,
            device_class,
            attribute,
        )

    def __repr__(self) -> str:
        """Representation of Translated state attribute."""
        return "<template StateAttrTranslated>"


class DomainStates:
    """Class to expose a specific HA domain as attributes."""

    __slots__ = ("_domain", "_hass")

    __setitem__ = _readonly
    __delitem__ = _readonly

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the domain states."""
        self._hass = hass
        self._domain = domain

    def __getattr__(self, name: str) -> TemplateState | None:
        """Return the states."""
        return _get_state_if_valid(self._hass, f"{self._domain}.{name}")

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    __getitem__ = __getattr__

    def _collect_domain(self) -> None:
        if (entity_collect := render_info_cv.get()) is not None:
            entity_collect.domains.add(self._domain)  # type: ignore[attr-defined]

    def _collect_domain_lifecycle(self) -> None:
        if (entity_collect := render_info_cv.get()) is not None:
            entity_collect.domains_lifecycle.add(self._domain)  # type: ignore[attr-defined]

    def __iter__(self) -> Generator[TemplateState]:
        """Return the iteration over all the states."""
        self._collect_domain()
        return _state_generator(self._hass, self._domain)

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_domain_lifecycle()
        return self._hass.states.async_entity_ids_count(self._domain)

    def __repr__(self) -> str:
        """Representation of Domain States."""
        return f"<template DomainStates('{self._domain}')>"


class TemplateStateBase(State):
    """Class to represent a state object in a template."""

    __slots__ = ("_collect", "_entity_id", "_hass", "_state")

    _state: State

    __setitem__ = _readonly
    __delitem__ = _readonly

    # Inheritance is done so functions that check against State keep working
    # pylint: disable-next=super-init-not-called
    def __init__(self, hass: HomeAssistant, collect: bool, entity_id: str) -> None:
        """Initialize template state."""
        self._hass = hass
        self._collect = collect
        self._entity_id = entity_id
        self._cache: dict[str, Any] = {}

    def _collect_state(self) -> None:
        if self._collect and (render_info := render_info_cv.get()):
            render_info.entities.add(self._entity_id)  # type: ignore[attr-defined]

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    def __getitem__(self, item: str) -> Any:
        """Return a property as an attribute for jinja."""
        if item in _COLLECTABLE_STATE_ATTRIBUTES:
            # _collect_state inlined here for performance
            if self._collect and (render_info := render_info_cv.get()):
                render_info.entities.add(self._entity_id)  # type: ignore[attr-defined]
            return getattr(self._state, item)
        if item == "entity_id":
            return self._entity_id
        if item == "state_with_unit":
            return self.state_with_unit
        raise KeyError

    @under_cached_property
    def entity_id(self) -> str:
        """Wrap State.entity_id.

        Intentionally does not collect state
        """
        return self._entity_id

    @property
    def state(self) -> str:  # type: ignore[override]
        """Wrap State.state."""
        self._collect_state()
        return self._state.state

    @property
    def attributes(self) -> ReadOnlyDict[str, Any]:  # type: ignore[override]
        """Wrap State.attributes."""
        self._collect_state()
        return self._state.attributes

    @property
    def last_changed(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_changed."""
        self._collect_state()
        return self._state.last_changed

    @property
    def last_reported(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_reported."""
        self._collect_state()
        return self._state.last_reported

    @property
    def last_updated(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_updated."""
        self._collect_state()
        return self._state.last_updated

    @property
    def context(self) -> Context:  # type: ignore[override]
        """Wrap State.context."""
        self._collect_state()
        return self._state.context

    @property
    def domain(self) -> str:  # type: ignore[override]
        """Wrap State.domain."""
        self._collect_state()
        return self._state.domain

    @property
    def object_id(self) -> str:  # type: ignore[override]
        """Wrap State.object_id."""
        self._collect_state()
        return self._state.object_id

    @property
    def name(self) -> str:
        """Wrap State.name."""
        self._collect_state()
        return self._state.name

    @property
    def state_with_unit(self) -> str:
        """Return the state concatenated with the unit if available."""
        return self.format_state(rounded=True, with_unit=True)

    def format_state(self, rounded: bool, with_unit: bool) -> str:
        """Return a formatted version of the state."""
        # Import here, not at top-level, to avoid circular import
        from homeassistant.components.sensor import (  # noqa: PLC0415
            DOMAIN as SENSOR_DOMAIN,
            async_rounded_state,
        )

        self._collect_state()
        if rounded and self._state.domain == SENSOR_DOMAIN:
            state = async_rounded_state(self._hass, self._entity_id, self._state)
        else:
            state = self._state.state
        if with_unit and (unit := self._state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
            return f"{state} {unit}"
        return state

    def __eq__(self, other: object) -> bool:
        """Ensure we collect on equality check."""
        self._collect_state()
        return self._state.__eq__(other)


class TemplateState(TemplateStateBase):
    """Class to represent a state object in a template."""

    __slots__ = ()

    # Inheritance is done so functions that check against State keep working
    def __init__(self, hass: HomeAssistant, state: State, collect: bool = True) -> None:
        """Initialize template state."""
        super().__init__(hass, collect, state.entity_id)
        self._state = state

    def __repr__(self) -> str:
        """Representation of Template State."""
        return f"<template TemplateState({self._state!r})>"


class TemplateStateFromEntityId(TemplateStateBase):
    """Class to represent a state object in a template."""

    __slots__ = ()

    def __init__(
        self, hass: HomeAssistant, entity_id: str, collect: bool = True
    ) -> None:
        """Initialize template state."""
        super().__init__(hass, collect, entity_id)

    @property
    def _state(self) -> State:  # type: ignore[override]
        state = self._hass.states.get(self._entity_id)
        if not state:
            state = State(self._entity_id, STATE_UNKNOWN)
        return state

    def __repr__(self) -> str:
        """Representation of Template State."""
        return f"<template TemplateStateFromEntityId({self._entity_id})>"


_create_template_state_no_collect = partial(TemplateState, collect=False)


def _collect_state(hass: HomeAssistant, entity_id: str) -> None:
    if (entity_collect := render_info_cv.get()) is not None:
        entity_collect.entities.add(entity_id)  # type: ignore[attr-defined]


def _state_generator(
    hass: HomeAssistant, domain: str | None
) -> Generator[TemplateState]:
    """State generator for a domain or all states."""
    states = hass.states
    # If domain is None, we want to iterate over all states, but making
    # a copy of the dict is expensive. So we iterate over the protected
    # _states dict instead. This is safe because we're not modifying it
    # and everything is happening in the same thread (MainThread).
    #
    # We do not want to expose this method in the public API though to
    # ensure it does not get misused.
    #
    container: Iterable[State]
    if domain is None:
        container = states._states.values()  # noqa: SLF001
    else:
        container = states.async_all(domain)
    for state in container:
        yield _template_state_no_collect(hass, state)


def _get_state_if_valid(hass: HomeAssistant, entity_id: str) -> TemplateState | None:
    state = hass.states.get(entity_id)
    if state is None and not valid_entity_id(entity_id):
        raise TemplateError(f"Invalid entity ID '{entity_id}'")
    return _get_template_state_from_state(hass, entity_id, state)


def _get_state(hass: HomeAssistant, entity_id: str) -> TemplateState | None:
    return _get_template_state_from_state(hass, entity_id, hass.states.get(entity_id))


def _get_template_state_from_state(
    hass: HomeAssistant, entity_id: str, state: State | None
) -> TemplateState | None:
    if state is None:
        # Only need to collect if none, if not none collect first actual
        # access to the state properties in the state wrapper.
        _collect_state(hass, entity_id)
        return None
    return _template_state(hass, state)


def _resolve_state(
    hass: HomeAssistant, entity_id_or_state: Any
) -> State | TemplateState | None:
    """Return state or entity_id if given."""
    if isinstance(entity_id_or_state, State):
        return entity_id_or_state
    if isinstance(entity_id_or_state, str):
        return _get_state(hass, entity_id_or_state)
    return None
