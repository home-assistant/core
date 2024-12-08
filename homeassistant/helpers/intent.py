"""Module to coordinate user intentions."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Collection, Coroutine, Iterable
import dataclasses
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from itertools import groupby
import logging
from typing import Any

from propcache import cached_property
import voluptuous as vol

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey

from . import (
    area_registry,
    config_validation as cv,
    device_registry,
    entity_registry,
    floor_registry,
)
from .typing import VolSchemaType

_LOGGER = logging.getLogger(__name__)
type _SlotsType = dict[str, Any]
type _IntentSlotsType = dict[
    str | tuple[str, str], VolSchemaType | Callable[[Any], Any]
]

INTENT_TURN_OFF = "HassTurnOff"
INTENT_TURN_ON = "HassTurnOn"
INTENT_TOGGLE = "HassToggle"
INTENT_GET_STATE = "HassGetState"
INTENT_NEVERMIND = "HassNevermind"
INTENT_SET_POSITION = "HassSetPosition"
INTENT_START_TIMER = "HassStartTimer"
INTENT_CANCEL_TIMER = "HassCancelTimer"
INTENT_CANCEL_ALL_TIMERS = "HassCancelAllTimers"
INTENT_INCREASE_TIMER = "HassIncreaseTimer"
INTENT_DECREASE_TIMER = "HassDecreaseTimer"
INTENT_PAUSE_TIMER = "HassPauseTimer"
INTENT_UNPAUSE_TIMER = "HassUnpauseTimer"
INTENT_TIMER_STATUS = "HassTimerStatus"
INTENT_GET_CURRENT_DATE = "HassGetCurrentDate"
INTENT_GET_CURRENT_TIME = "HassGetCurrentTime"
INTENT_RESPOND = "HassRespond"

SLOT_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

DATA_KEY: HassKey[dict[str, IntentHandler]] = HassKey("intent")

SPEECH_TYPE_PLAIN = "plain"
SPEECH_TYPE_SSML = "ssml"


@callback
@bind_hass
def async_register(hass: HomeAssistant, handler: IntentHandler) -> None:
    """Register an intent with Home Assistant."""
    if (intents := hass.data.get(DATA_KEY)) is None:
        intents = {}
        hass.data[DATA_KEY] = intents

    assert getattr(handler, "intent_type", None), "intent_type should be set"

    if handler.intent_type in intents:
        _LOGGER.warning(
            "Intent %s is being overwritten by %s", handler.intent_type, handler
        )

    intents[handler.intent_type] = handler


@callback
@bind_hass
def async_remove(hass: HomeAssistant, intent_type: str) -> None:
    """Remove an intent from Home Assistant."""
    if (intents := hass.data.get(DATA_KEY)) is None:
        return

    intents.pop(intent_type, None)


@callback
def async_get(hass: HomeAssistant) -> Iterable[IntentHandler]:
    """Return registered intents."""
    return hass.data.get(DATA_KEY, {}).values()


@bind_hass
async def async_handle(
    hass: HomeAssistant,
    platform: str,
    intent_type: str,
    slots: _SlotsType | None = None,
    text_input: str | None = None,
    context: Context | None = None,
    language: str | None = None,
    assistant: str | None = None,
    device_id: str | None = None,
    conversation_agent_id: str | None = None,
) -> IntentResponse:
    """Handle an intent."""
    handler = hass.data.get(DATA_KEY, {}).get(intent_type)

    if handler is None:
        raise UnknownIntent(f"Unknown intent {intent_type}")

    if context is None:
        context = Context()

    if language is None:
        language = hass.config.language

    intent = Intent(
        hass,
        platform=platform,
        intent_type=intent_type,
        slots=slots or {},
        text_input=text_input,
        context=context,
        language=language,
        assistant=assistant,
        device_id=device_id,
        conversation_agent_id=conversation_agent_id,
    )

    try:
        _LOGGER.info("Triggering intent handler %s", handler)
        result = await handler.async_handle(intent)
    except vol.Invalid as err:
        _LOGGER.warning("Received invalid slot info for %s: %s", intent_type, err)
        raise InvalidSlotInfo(f"Received invalid slot info for {intent_type}") from err
    except IntentError:
        raise  # bubble up intent related errors
    except Exception as err:
        _LOGGER.exception("Error handling %s", intent_type)
        raise IntentUnexpectedError(f"Error handling {intent_type}") from err
    return result


class IntentError(HomeAssistantError):
    """Base class for intent related errors."""


class UnknownIntent(IntentError):
    """When the intent is not registered."""


class InvalidSlotInfo(IntentError):
    """When the slot data is invalid."""


class IntentHandleError(IntentError):
    """Error while handling intent."""

    def __init__(self, message: str = "", response_key: str | None = None) -> None:
        """Initialize error."""
        super().__init__(message)
        self.response_key = response_key


class IntentUnexpectedError(IntentError):
    """Unexpected error while handling intent."""


class MatchFailedReason(Enum):
    """Possible reasons for match failure in async_match_targets."""

    NAME = auto()
    """No entities matched name constraint."""

    AREA = auto()
    """No entities matched area constraint."""

    FLOOR = auto()
    """No entities matched floor constraint."""

    DOMAIN = auto()
    """No entities matched domain constraint."""

    DEVICE_CLASS = auto()
    """No entities matched device class constraint."""

    FEATURE = auto()
    """No entities matched supported features constraint."""

    STATE = auto()
    """No entities matched required states constraint."""

    ASSISTANT = auto()
    """No entities matched exposed to assistant constraint."""

    INVALID_AREA = auto()
    """Area name from constraint does not exist."""

    INVALID_FLOOR = auto()
    """Floor name from constraint does not exist."""

    DUPLICATE_NAME = auto()
    """Two or more entities matched the same name constraint and could not be disambiguated."""

    def is_no_entities_reason(self) -> bool:
        """Return True if the match failed because no entities matched."""
        return self not in (
            MatchFailedReason.INVALID_AREA,
            MatchFailedReason.INVALID_FLOOR,
            MatchFailedReason.DUPLICATE_NAME,
        )


@dataclass
class MatchTargetsConstraints:
    """Constraints for async_match_targets."""

    name: str | None = None
    """Entity name or alias."""

    area_name: str | None = None
    """Area name, id, or alias."""

    floor_name: str | None = None
    """Floor name, id, or alias."""

    domains: Collection[str] | None = None
    """Domain names."""

    device_classes: Collection[str] | None = None
    """Device class names."""

    features: int | None = None
    """Required supported features."""

    states: Collection[str] | None = None
    """Required states for entities."""

    assistant: str | None = None
    """Name of assistant that entities should be exposed to."""

    allow_duplicate_names: bool = False
    """True if entities with duplicate names are allowed in result."""

    @property
    def has_constraints(self) -> bool:
        """Returns True if at least one constraint is set (ignores assistant)."""
        return bool(
            self.name
            or self.area_name
            or self.floor_name
            or self.domains
            or self.device_classes
            or self.features
            or self.states
        )


@dataclass
class MatchTargetsPreferences:
    """Preferences used to disambiguate duplicate name matches in async_match_targets."""

    area_id: str | None = None
    """Id of area to use when deduplicating names."""

    floor_id: str | None = None
    """Id of floor to use when deduplicating names."""


@dataclass
class MatchTargetsResult:
    """Result from async_match_targets."""

    is_match: bool
    """True if one or more entities matched."""

    no_match_reason: MatchFailedReason | None = None
    """Reason for failed match when is_match = False."""

    states: list[State] = field(default_factory=list)
    """List of matched entity states when is_match = True."""

    no_match_name: str | None = None
    """Name of invalid area/floor or duplicate name when match fails for those reasons."""

    areas: list[area_registry.AreaEntry] = field(default_factory=list)
    """Areas that were targeted."""

    floors: list[floor_registry.FloorEntry] = field(default_factory=list)
    """Floors that were targeted."""


class MatchFailedError(IntentError):
    """Error when target matching fails."""

    def __init__(
        self,
        result: MatchTargetsResult,
        constraints: MatchTargetsConstraints,
        preferences: MatchTargetsPreferences | None = None,
    ) -> None:
        """Initialize error."""
        super().__init__()

        self.result = result
        self.constraints = constraints
        self.preferences = preferences

    def __str__(self) -> str:
        """Return string representation."""
        return f"<MatchFailedError result={self.result}, constraints={self.constraints}, preferences={self.preferences}>"


class NoStatesMatchedError(MatchFailedError):
    """Error when no states match the intent's constraints."""

    def __init__(
        self,
        reason: MatchFailedReason,
        name: str | None = None,
        area: str | None = None,
        floor: str | None = None,
        domains: set[str] | None = None,
        device_classes: set[str] | None = None,
    ) -> None:
        """Initialize error."""
        super().__init__(
            result=MatchTargetsResult(False, reason),
            constraints=MatchTargetsConstraints(
                name=name,
                area_name=area,
                floor_name=floor,
                domains=domains,
                device_classes=device_classes,
            ),
        )


@dataclass
class MatchTargetsCandidate:
    """Candidate for async_match_targets."""

    state: State
    is_exposed: bool
    entity: entity_registry.RegistryEntry | None = None
    area: area_registry.AreaEntry | None = None
    floor: floor_registry.FloorEntry | None = None
    device: device_registry.DeviceEntry | None = None
    matched_name: str | None = None


def find_areas(
    name: str, areas: area_registry.AreaRegistry
) -> Iterable[area_registry.AreaEntry]:
    """Find all areas matching a name (including aliases)."""
    name_norm = _normalize_name(name)
    for area in areas.async_list_areas():
        # Accept name or area id
        if (area.id == name) or (_normalize_name(area.name) == name_norm):
            yield area
            continue

        if not area.aliases:
            continue

        for alias in area.aliases:
            if _normalize_name(alias) == name_norm:
                yield area
                break


def find_floors(
    name: str, floors: floor_registry.FloorRegistry
) -> Iterable[floor_registry.FloorEntry]:
    """Find all floors matching a name (including aliases)."""
    name_norm = _normalize_name(name)
    for floor in floors.async_list_floors():
        # Accept name or floor id
        if (floor.floor_id == name) or (_normalize_name(floor.name) == name_norm):
            yield floor
            continue

        if not floor.aliases:
            continue

        for alias in floor.aliases:
            if _normalize_name(alias) == name_norm:
                yield floor
                break


def _normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    return name.strip().casefold()


def _filter_by_name(
    name: str,
    candidates: Iterable[MatchTargetsCandidate],
) -> Iterable[MatchTargetsCandidate]:
    """Filter candidates by name."""
    name_norm = _normalize_name(name)

    for candidate in candidates:
        # Accept name or entity id
        if (candidate.state.entity_id == name) or _normalize_name(
            candidate.state.name
        ) == name_norm:
            candidate.matched_name = name
            yield candidate
            continue

        if candidate.entity is None:
            continue

        if candidate.entity.name and (
            _normalize_name(candidate.entity.name) == name_norm
        ):
            candidate.matched_name = name
            yield candidate
            continue

        # Check aliases
        if candidate.entity.aliases:
            for alias in candidate.entity.aliases:
                if _normalize_name(alias) == name_norm:
                    candidate.matched_name = name
                    yield candidate
                    break


def _filter_by_features(
    features: int,
    candidates: Iterable[MatchTargetsCandidate],
) -> Iterable[MatchTargetsCandidate]:
    """Filter candidates by supported features."""
    for candidate in candidates:
        if (candidate.entity is not None) and (
            (candidate.entity.supported_features & features) == features
        ):
            yield candidate
            continue

        supported_features = candidate.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if (supported_features & features) == features:
            yield candidate


def _filter_by_device_classes(
    device_classes: Iterable[str],
    candidates: Iterable[MatchTargetsCandidate],
) -> Iterable[MatchTargetsCandidate]:
    """Filter candidates by device classes."""
    for candidate in candidates:
        if (
            (candidate.entity is not None)
            and candidate.entity.device_class
            and (candidate.entity.device_class in device_classes)
        ):
            yield candidate
            continue

        device_class = candidate.state.attributes.get(ATTR_DEVICE_CLASS)
        if device_class and (device_class in device_classes):
            yield candidate


def _add_areas(
    areas: area_registry.AreaRegistry,
    devices: device_registry.DeviceRegistry,
    candidates: Iterable[MatchTargetsCandidate],
) -> None:
    """Add area and device entries to match candidates."""
    for candidate in candidates:
        if candidate.entity is None:
            continue

        if candidate.entity.device_id:
            candidate.device = devices.async_get(candidate.entity.device_id)

        if candidate.entity.area_id:
            # Use entity area first
            candidate.area = areas.async_get_area(candidate.entity.area_id)
            assert candidate.area is not None
        elif (candidate.device is not None) and candidate.device.area_id:
            # Fall back to device area
            candidate.area = areas.async_get_area(candidate.device.area_id)


@callback
def async_match_targets(  # noqa: C901
    hass: HomeAssistant,
    constraints: MatchTargetsConstraints,
    preferences: MatchTargetsPreferences | None = None,
    states: list[State] | None = None,
) -> MatchTargetsResult:
    """Match entities based on constraints in order to handle an intent."""
    preferences = preferences or MatchTargetsPreferences()
    filtered_by_domain = False

    if not states:
        # Get all states and filter by domain
        states = hass.states.async_all(constraints.domains)
        filtered_by_domain = True
        if not states:
            return MatchTargetsResult(False, MatchFailedReason.DOMAIN)

    candidates = [
        MatchTargetsCandidate(
            state=state,
            is_exposed=(
                async_should_expose(hass, constraints.assistant, state.entity_id)
                if constraints.assistant
                else True
            ),
        )
        for state in states
    ]

    if constraints.domains and (not filtered_by_domain):
        # Filter by domain (if we didn't already do it)
        candidates = [c for c in candidates if c.state.domain in constraints.domains]
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.DOMAIN)

    if constraints.states:
        # Filter by state
        candidates = [c for c in candidates if c.state.state in constraints.states]
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.STATE)

    # Try to exit early so we can avoid registry lookups
    if not (
        constraints.name
        or constraints.features
        or constraints.device_classes
        or constraints.area_name
        or constraints.floor_name
    ):
        if constraints.assistant:
            # Check exposure
            candidates = [c for c in candidates if c.is_exposed]
            if not candidates:
                return MatchTargetsResult(False, MatchFailedReason.ASSISTANT)

        return MatchTargetsResult(True, states=[c.state for c in candidates])

    # We need entity registry entries now
    er = entity_registry.async_get(hass)
    for candidate in candidates:
        candidate.entity = er.async_get(candidate.state.entity_id)

    if constraints.name:
        # Filter by entity name or alias
        candidates = list(_filter_by_name(constraints.name, candidates))
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.NAME)

    if constraints.features:
        # Filter by supported features
        candidates = list(_filter_by_features(constraints.features, candidates))
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.FEATURE)

    if constraints.device_classes:
        # Filter by device class
        candidates = list(
            _filter_by_device_classes(constraints.device_classes, candidates)
        )
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.DEVICE_CLASS)

    # Check floor/area constraints
    targeted_floors: list[floor_registry.FloorEntry] | None = None
    targeted_areas: list[area_registry.AreaEntry] | None = None

    # True when area information has been added to candidates
    areas_added = False

    if constraints.floor_name or constraints.area_name:
        ar = area_registry.async_get(hass)
        dr = device_registry.async_get(hass)
        _add_areas(ar, dr, candidates)
        areas_added = True

        if constraints.floor_name:
            # Filter by areas associated with floor
            fr = floor_registry.async_get(hass)
            targeted_floors = list(find_floors(constraints.floor_name, fr))
            if not targeted_floors:
                return MatchTargetsResult(
                    False,
                    MatchFailedReason.INVALID_FLOOR,
                    no_match_name=constraints.floor_name,
                )

            possible_floor_ids = {floor.floor_id for floor in targeted_floors}
            possible_area_ids = {
                area.id
                for area in ar.async_list_areas()
                if area.floor_id in possible_floor_ids
            }

            candidates = [
                c
                for c in candidates
                if (c.area is not None) and (c.area.id in possible_area_ids)
            ]
            if not candidates:
                return MatchTargetsResult(
                    False, MatchFailedReason.FLOOR, floors=targeted_floors
                )
        else:
            # All areas are possible
            possible_area_ids = {area.id for area in ar.async_list_areas()}

        if constraints.area_name:
            targeted_areas = list(find_areas(constraints.area_name, ar))
            if not targeted_areas:
                return MatchTargetsResult(
                    False,
                    MatchFailedReason.INVALID_AREA,
                    no_match_name=constraints.area_name,
                )

            matching_area_ids = {area.id for area in targeted_areas}

            # May be constrained by floors above
            possible_area_ids.intersection_update(matching_area_ids)
            candidates = [
                c
                for c in candidates
                if (c.area is not None) and (c.area.id in possible_area_ids)
            ]
            if not candidates:
                return MatchTargetsResult(
                    False, MatchFailedReason.AREA, areas=targeted_areas
                )

    if constraints.assistant:
        # Check exposure
        candidates = [c for c in candidates if c.is_exposed]
        if not candidates:
            return MatchTargetsResult(False, MatchFailedReason.ASSISTANT)

    if constraints.name and (not constraints.allow_duplicate_names):
        # Check for duplicates
        if not areas_added:
            ar = area_registry.async_get(hass)
            dr = device_registry.async_get(hass)
            _add_areas(ar, dr, candidates)
            areas_added = True

        sorted_candidates = sorted(
            [c for c in candidates if c.matched_name],
            key=lambda c: c.matched_name or "",
        )
        final_candidates: list[MatchTargetsCandidate] = []
        for name, group in groupby(sorted_candidates, key=lambda c: c.matched_name):
            group_candidates = list(group)
            if len(group_candidates) < 2:
                # No duplicates for name
                final_candidates.extend(group_candidates)
                continue

            # Try to disambiguate by preferences
            if preferences.floor_id:
                group_candidates = [
                    c
                    for c in group_candidates
                    if (c.area is not None)
                    and (c.area.floor_id == preferences.floor_id)
                ]
                if len(group_candidates) < 2:
                    # Disambiguated by floor
                    final_candidates.extend(group_candidates)
                    continue

            if preferences.area_id:
                group_candidates = [
                    c
                    for c in group_candidates
                    if (c.area is not None) and (c.area.id == preferences.area_id)
                ]
                if len(group_candidates) < 2:
                    # Disambiguated by area
                    final_candidates.extend(group_candidates)
                    continue

            # Couldn't disambiguate duplicate names
            return MatchTargetsResult(
                False,
                MatchFailedReason.DUPLICATE_NAME,
                no_match_name=name,
                areas=targeted_areas or [],
                floors=targeted_floors or [],
            )

        if not final_candidates:
            return MatchTargetsResult(
                False,
                MatchFailedReason.NAME,
                areas=targeted_areas or [],
                floors=targeted_floors or [],
            )

        candidates = final_candidates

    return MatchTargetsResult(
        True,
        None,
        states=[c.state for c in candidates],
        areas=targeted_areas or [],
        floors=targeted_floors or [],
    )


@callback
@bind_hass
def async_match_states(
    hass: HomeAssistant,
    name: str | None = None,
    area_name: str | None = None,
    floor_name: str | None = None,
    domains: Collection[str] | None = None,
    device_classes: Collection[str] | None = None,
    states: list[State] | None = None,
    assistant: str | None = None,
) -> Iterable[State]:
    """Simplified interface to async_match_targets that returns states matching the constraints."""
    result = async_match_targets(
        hass,
        constraints=MatchTargetsConstraints(
            name=name,
            area_name=area_name,
            floor_name=floor_name,
            domains=domains,
            device_classes=device_classes,
            assistant=assistant,
        ),
        states=states,
    )
    return result.states


@callback
def async_test_feature(state: State, feature: int, feature_name: str) -> None:
    """Test if state supports a feature."""
    if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & feature == 0:
        raise IntentHandleError(f"Entity {state.name} does not support {feature_name}")


class IntentHandler:
    """Intent handler registration."""

    intent_type: str
    platforms: set[str] | None = None
    description: str | None = None

    @property
    def slot_schema(self) -> dict | None:
        """Return a slot schema."""
        return None

    @callback
    def async_can_handle(self, intent_obj: Intent) -> bool:
        """Test if an intent can be handled."""
        return self.platforms is None or intent_obj.platform in self.platforms

    @callback
    def async_validate_slots(self, slots: _SlotsType) -> _SlotsType:
        """Validate slot information."""
        if self.slot_schema is None:
            return slots

        return self._slot_schema(slots)  # type: ignore[no-any-return]

    @cached_property
    def _slot_schema(self) -> vol.Schema:
        """Create validation schema for slots."""
        assert self.slot_schema is not None
        return vol.Schema(
            {
                key: SLOT_SCHEMA.extend({"value": validator})
                for key, validator in self.slot_schema.items()
            },
            extra=vol.ALLOW_EXTRA,
        )

    async def async_handle(self, intent_obj: Intent) -> IntentResponse:
        """Handle the intent."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Represent a string of an intent handler."""
        return f"<{self.__class__.__name__} - {self.intent_type}>"


def non_empty_string(value: Any) -> str:
    """Coerce value to string and fail if string is empty or whitespace."""
    value_str = cv.string(value)
    if not value_str.strip():
        raise vol.Invalid("string value is empty")

    return value_str


class DynamicServiceIntentHandler(IntentHandler):
    """Service Intent handler registration (dynamic).

    Service specific intent handler that calls a service by name/entity_id.
    """

    # We use a small timeout in service calls to (hopefully) pass validation
    # checks, but not try to wait for the call to fully complete.
    service_timeout: float = 0.2

    def __init__(
        self,
        intent_type: str,
        speech: str | None = None,
        required_slots: _IntentSlotsType | None = None,
        optional_slots: _IntentSlotsType | None = None,
        required_domains: set[str] | None = None,
        required_features: int | None = None,
        required_states: set[str] | None = None,
        description: str | None = None,
        platforms: set[str] | None = None,
        device_classes: set[type[StrEnum]] | None = None,
    ) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.speech = speech
        self.required_domains = required_domains
        self.required_features = required_features
        self.required_states = required_states
        self.description = description
        self.platforms = platforms
        self.device_classes = device_classes

        self.required_slots: _IntentSlotsType = {}
        if required_slots:
            for key, value_schema in required_slots.items():
                if isinstance(key, str):
                    # Slot name/service data key
                    key = (key, key)

                self.required_slots[key] = value_schema

        self.optional_slots: _IntentSlotsType = {}
        if optional_slots:
            for key, value_schema in optional_slots.items():
                if isinstance(key, str):
                    # Slot name/service data key
                    key = (key, key)

                self.optional_slots[key] = value_schema

    @cached_property
    def slot_schema(self) -> dict:
        """Return a slot schema."""
        domain_validator = (
            vol.In(list(self.required_domains)) if self.required_domains else cv.string
        )
        slot_schema = {
            vol.Any("name", "area", "floor"): non_empty_string,
            vol.Optional("domain"): vol.All(cv.ensure_list, [domain_validator]),
        }
        if self.device_classes:
            # The typical way to match enums is with vol.Coerce, but we build a
            # flat list to make the API simpler to describe programmatically
            flattened_device_classes = vol.In(
                [
                    device_class.value
                    for device_class_enum in self.device_classes
                    for device_class in device_class_enum
                ]
            )
            slot_schema.update(
                {
                    vol.Optional("device_class"): vol.All(
                        cv.ensure_list,
                        [flattened_device_classes],
                    )
                }
            )

        slot_schema.update(
            {
                vol.Optional("preferred_area_id"): cv.string,
                vol.Optional("preferred_floor_id"): cv.string,
            }
        )

        if self.required_slots:
            slot_schema.update(
                {
                    vol.Required(key[0]): validator
                    for key, validator in self.required_slots.items()
                }
            )

        if self.optional_slots:
            slot_schema.update(
                {
                    vol.Optional(key[0]): validator
                    for key, validator in self.optional_slots.items()
                }
            )

        return slot_schema

    @abstractmethod
    def get_domain_and_service(
        self, intent_obj: Intent, state: State
    ) -> tuple[str, str]:
        """Get the domain and service name to call."""
        raise NotImplementedError

    async def async_handle(self, intent_obj: Intent) -> IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        name_slot = slots.get("name", {})
        entity_name: str | None = name_slot.get("value")
        entity_text: str | None = name_slot.get("text")
        if entity_name == "all":
            # Don't match on name if targeting all entities
            entity_name = None

        # Get area/floor info
        area_slot = slots.get("area", {})
        area_id = area_slot.get("value")

        floor_slot = slots.get("floor", {})
        floor_id = floor_slot.get("value")

        # Optional domain/device class filters.
        # Convert to sets for speed.
        domains: set[str] | None = self.required_domains
        device_classes: set[str] | None = None

        if "domain" in slots:
            domains = set(slots["domain"]["value"])

        if "device_class" in slots:
            device_classes = set(slots["device_class"]["value"])

        match_constraints = MatchTargetsConstraints(
            name=entity_name,
            area_name=area_id,
            floor_name=floor_id,
            domains=domains,
            device_classes=device_classes,
            assistant=intent_obj.assistant,
            features=self.required_features,
            states=self.required_states,
        )
        if not match_constraints.has_constraints:
            # Fail if attempting to target all devices in the house
            raise IntentHandleError("Service handler cannot target all devices")

        match_preferences = MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )

        match_result = async_match_targets(hass, match_constraints, match_preferences)
        if not match_result.is_match:
            raise MatchFailedError(
                result=match_result,
                constraints=match_constraints,
                preferences=match_preferences,
            )

        # Ensure name is text
        if ("name" in slots) and entity_text:
            slots["name"]["value"] = entity_text

        # Replace area/floor values with the resolved ids for use in templates
        if ("area" in slots) and match_result.areas:
            slots["area"]["value"] = match_result.areas[0].id

        if ("floor" in slots) and match_result.floors:
            slots["floor"]["value"] = match_result.floors[0].floor_id

        # Update intent slots to include any transformations done by the schemas
        intent_obj.slots = slots

        response = await self.async_handle_states(
            intent_obj, match_result, match_constraints, match_preferences
        )

        # Make the matched states available in the response
        response.async_set_states(
            matched_states=match_result.states, unmatched_states=[]
        )

        return response

    async def async_handle_states(
        self,
        intent_obj: Intent,
        match_result: MatchTargetsResult,
        match_constraints: MatchTargetsConstraints,
        match_preferences: MatchTargetsPreferences | None = None,
    ) -> IntentResponse:
        """Complete action on matched entity states."""
        states = match_result.states
        response = intent_obj.create_response()

        hass = intent_obj.hass
        success_results: list[IntentResponseTarget] = []

        if match_result.floors:
            success_results.extend(
                IntentResponseTarget(
                    type=IntentResponseTargetType.FLOOR,
                    name=floor.name,
                    id=floor.floor_id,
                )
                for floor in match_result.floors
            )
            speech_name = match_result.floors[0].name
        elif match_result.areas:
            success_results.extend(
                IntentResponseTarget(
                    type=IntentResponseTargetType.AREA, name=area.name, id=area.id
                )
                for area in match_result.areas
            )
            speech_name = match_result.areas[0].name
        else:
            speech_name = states[0].name

        service_coros: list[Coroutine[Any, Any, None]] = []
        for state in states:
            domain, service = self.get_domain_and_service(intent_obj, state)
            service_coros.append(
                self.async_call_service(domain, service, intent_obj, state)
            )

        # Handle service calls in parallel, noting failures as they occur.
        failed_results: list[IntentResponseTarget] = []
        for state, service_coro in zip(
            states, asyncio.as_completed(service_coros), strict=False
        ):
            target = IntentResponseTarget(
                type=IntentResponseTargetType.ENTITY,
                name=state.name,
                id=state.entity_id,
            )

            try:
                await service_coro
                success_results.append(target)
            except Exception:
                failed_results.append(target)
                _LOGGER.exception("Service call failed for %s", state.entity_id)

        if not success_results:
            # If no entities succeeded, raise an error.
            failed_entity_ids = [target.id for target in failed_results]
            raise IntentHandleError(
                f"Failed to call {service} for: {failed_entity_ids}"
            )

        response.async_set_results(
            success_results=success_results, failed_results=failed_results
        )

        # Update all states
        states = [hass.states.get(state.entity_id) or state for state in states]
        response.async_set_states(states)

        if self.speech is not None:
            response.async_set_speech(self.speech.format(speech_name))

        return response

    async def async_call_service(
        self, domain: str, service: str, intent_obj: Intent, state: State
    ) -> None:
        """Call service on entity."""
        hass = intent_obj.hass

        service_data: dict[str, Any] = {ATTR_ENTITY_ID: state.entity_id}
        if self.required_slots:
            service_data.update(
                {
                    key[1]: intent_obj.slots[key[0]]["value"]
                    for key in self.required_slots
                }
            )

        if self.optional_slots:
            for key in self.optional_slots:
                value = intent_obj.slots.get(key[0])
                if value:
                    service_data[key[1]] = value["value"]

        await self._run_then_background(
            hass.async_create_task_internal(
                hass.services.async_call(
                    domain,
                    service,
                    service_data,
                    context=intent_obj.context,
                    blocking=True,
                ),
                f"intent_call_service_{domain}_{service}",
            )
        )

    async def _run_then_background(self, task: asyncio.Task[Any]) -> None:
        """Run task with timeout to (hopefully) catch validation errors.

        After the timeout the task will continue to run in the background.
        """
        try:
            await asyncio.wait({task}, timeout=self.service_timeout)
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            # Task calling us was cancelled, so cancel service call task, and wait for
            # it to be cancelled, within reason, before leaving.
            _LOGGER.debug("Service call was cancelled: %s", task.get_name())
            task.cancel()
            await asyncio.wait({task}, timeout=5)
            raise


class ServiceIntentHandler(DynamicServiceIntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    def __init__(
        self,
        intent_type: str,
        domain: str,
        service: str,
        speech: str | None = None,
        required_slots: _IntentSlotsType | None = None,
        optional_slots: _IntentSlotsType | None = None,
        required_domains: set[str] | None = None,
        required_features: int | None = None,
        required_states: set[str] | None = None,
        description: str | None = None,
        platforms: set[str] | None = None,
        device_classes: set[type[StrEnum]] | None = None,
    ) -> None:
        """Create service handler."""
        super().__init__(
            intent_type,
            speech=speech,
            required_slots=required_slots,
            optional_slots=optional_slots,
            required_domains=required_domains,
            required_features=required_features,
            required_states=required_states,
            description=description,
            platforms=platforms,
            device_classes=device_classes,
        )
        self.domain = domain
        self.service = service

    def get_domain_and_service(
        self, intent_obj: Intent, state: State
    ) -> tuple[str, str]:
        """Get the domain and service name to call."""
        return (self.domain, self.service)


class IntentCategory(Enum):
    """Category of an intent."""

    ACTION = "action"
    """Trigger an action like turning an entity on or off"""

    QUERY = "query"
    """Get information about the state of an entity"""


class Intent:
    """Hold the intent."""

    __slots__ = [
        "hass",
        "platform",
        "intent_type",
        "slots",
        "text_input",
        "context",
        "language",
        "category",
        "assistant",
        "device_id",
        "conversation_agent_id",
    ]

    def __init__(
        self,
        hass: HomeAssistant,
        platform: str,
        intent_type: str,
        slots: _SlotsType,
        text_input: str | None,
        context: Context,
        language: str,
        category: IntentCategory | None = None,
        assistant: str | None = None,
        device_id: str | None = None,
        conversation_agent_id: str | None = None,
    ) -> None:
        """Initialize an intent."""
        self.hass = hass
        self.platform = platform
        self.intent_type = intent_type
        self.slots = slots
        self.text_input = text_input
        self.context = context
        self.language = language
        self.category = category
        self.assistant = assistant
        self.device_id = device_id
        self.conversation_agent_id = conversation_agent_id

    @callback
    def create_response(self) -> IntentResponse:
        """Create a response."""
        return IntentResponse(language=self.language, intent=self)


class IntentResponseType(Enum):
    """Type of the intent response."""

    ACTION_DONE = "action_done"
    """Intent caused an action to occur"""

    PARTIAL_ACTION_DONE = "partial_action_done"
    """Intent caused an action, but it could only be partially done"""

    QUERY_ANSWER = "query_answer"
    """Response is an answer to a query"""

    ERROR = "error"
    """Response is an error"""


class IntentResponseErrorCode(str, Enum):
    """Reason for an intent response error."""

    NO_INTENT_MATCH = "no_intent_match"
    """Text could not be matched to an intent"""

    NO_VALID_TARGETS = "no_valid_targets"
    """Intent was matched, but no valid areas/devices/entities were targeted"""

    FAILED_TO_HANDLE = "failed_to_handle"
    """Unexpected error occurred while handling intent"""

    UNKNOWN = "unknown"
    """Error outside the scope of intent processing"""


class IntentResponseTargetType(str, Enum):
    """Type of target for an intent response."""

    AREA = "area"
    FLOOR = "floor"
    DEVICE = "device"
    ENTITY = "entity"
    DOMAIN = "domain"
    DEVICE_CLASS = "device_class"
    CUSTOM = "custom"


@dataclass(slots=True)
class IntentResponseTarget:
    """Target of the intent response."""

    name: str
    type: IntentResponseTargetType
    id: str | None = None


class IntentResponse:
    """Response to an intent."""

    def __init__(
        self,
        language: str,
        intent: Intent | None = None,
    ) -> None:
        """Initialize an IntentResponse."""
        self.language = language
        self.intent = intent
        self.speech: dict[str, dict[str, Any]] = {}
        self.reprompt: dict[str, dict[str, Any]] = {}
        self.card: dict[str, dict[str, str]] = {}
        self.error_code: IntentResponseErrorCode | None = None
        self.intent_targets: list[IntentResponseTarget] = []
        self.success_results: list[IntentResponseTarget] = []
        self.failed_results: list[IntentResponseTarget] = []
        self.matched_states: list[State] = []
        self.unmatched_states: list[State] = []
        self.speech_slots: dict[str, Any] = {}

        if (self.intent is not None) and (self.intent.category == IntentCategory.QUERY):
            # speech will be the answer to the query
            self.response_type = IntentResponseType.QUERY_ANSWER
        else:
            self.response_type = IntentResponseType.ACTION_DONE

    @callback
    def async_set_speech(
        self,
        speech: str,
        speech_type: str = "plain",
        extra_data: Any | None = None,
    ) -> None:
        """Set speech response."""
        self.speech[speech_type] = {
            "speech": speech,
            "extra_data": extra_data,
        }

    @callback
    def async_set_reprompt(
        self,
        speech: str,
        speech_type: str = "plain",
        extra_data: Any | None = None,
    ) -> None:
        """Set reprompt response."""
        self.reprompt[speech_type] = {
            "reprompt": speech,
            "extra_data": extra_data,
        }

    @callback
    def async_set_card(
        self, title: str, content: str, card_type: str = "simple"
    ) -> None:
        """Set card response."""
        self.card[card_type] = {"title": title, "content": content}

    @callback
    def async_set_error(self, code: IntentResponseErrorCode, message: str) -> None:
        """Set response error."""
        self.response_type = IntentResponseType.ERROR
        self.error_code = code

        # Speak error message
        self.async_set_speech(message)

    @callback
    def async_set_targets(
        self,
        intent_targets: list[IntentResponseTarget],
    ) -> None:
        """Set response targets."""
        self.intent_targets = intent_targets

    @callback
    def async_set_results(
        self,
        success_results: list[IntentResponseTarget],
        failed_results: list[IntentResponseTarget] | None = None,
    ) -> None:
        """Set response results."""
        self.success_results = success_results
        self.failed_results = failed_results if failed_results is not None else []

    @callback
    def async_set_states(
        self, matched_states: list[State], unmatched_states: list[State] | None = None
    ) -> None:
        """Set entity states that were matched or not matched during intent handling (query)."""
        self.matched_states = matched_states
        self.unmatched_states = unmatched_states or []

    @callback
    def async_set_speech_slots(self, speech_slots: dict[str, Any]) -> None:
        """Set slots that will be used in the response template of the default agent."""
        self.speech_slots = speech_slots

    @callback
    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of an intent response."""
        response_dict: dict[str, Any] = {
            "speech": self.speech,
            "card": self.card,
            "language": self.language,
            "response_type": self.response_type.value,
        }

        if self.reprompt:
            response_dict["reprompt"] = self.reprompt
        if self.speech_slots:
            response_dict["speech_slots"] = self.speech_slots

        response_data: dict[str, Any] = {}

        if self.response_type == IntentResponseType.ERROR:
            assert self.error_code is not None, "error code is required"
            response_data["code"] = self.error_code.value
        else:
            # action done or query answer
            response_data["targets"] = [
                dataclasses.asdict(target) for target in self.intent_targets
            ]

            # Add success/failed targets
            response_data["success"] = [
                dataclasses.asdict(target) for target in self.success_results
            ]

            response_data["failed"] = [
                dataclasses.asdict(target) for target in self.failed_results
            ]

        response_dict["data"] = response_data

        return response_dict
