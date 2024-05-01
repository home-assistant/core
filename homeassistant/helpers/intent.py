"""Module to coordinate user intentions."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Collection, Coroutine, Iterable
import dataclasses
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
import logging
from typing import Any

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

from . import (
    area_registry,
    config_validation as cv,
    device_registry,
    entity_registry,
    floor_registry,
)

_LOGGER = logging.getLogger(__name__)
_SlotsType = dict[str, Any]

INTENT_TURN_OFF = "HassTurnOff"
INTENT_TURN_ON = "HassTurnOn"
INTENT_TOGGLE = "HassToggle"
INTENT_GET_STATE = "HassGetState"
INTENT_NEVERMIND = "HassNevermind"
INTENT_SET_POSITION = "HassSetPosition"

SLOT_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

DATA_KEY = "intent"

SPEECH_TYPE_PLAIN = "plain"
SPEECH_TYPE_SSML = "ssml"


@callback
@bind_hass
def async_register(hass: HomeAssistant, handler: IntentHandler) -> None:
    """Register an intent with Home Assistant."""
    if (intents := hass.data.get(DATA_KEY)) is None:
        intents = hass.data[DATA_KEY] = {}

    assert handler.intent_type is not None, "intent_type cannot be None"

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
) -> IntentResponse:
    """Handle an intent."""
    handler: IntentHandler = hass.data.get(DATA_KEY, {}).get(intent_type)

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


class IntentUnexpectedError(IntentError):
    """Unexpected error while handling intent."""


class NoStatesMatchedError(IntentError):
    """Error when no states match the intent's constraints."""

    def __init__(
        self,
        name: str | None = None,
        area: str | None = None,
        floor: str | None = None,
        domains: set[str] | None = None,
        device_classes: set[str] | None = None,
    ) -> None:
        """Initialize error."""
        super().__init__()

        self.name = name
        self.area = area
        self.floor = floor
        self.domains = domains
        self.device_classes = device_classes


class DuplicateNamesMatchedError(IntentError):
    """Error when two or more entities with the same name matched."""

    def __init__(self, name: str, area: str | None) -> None:
        """Initialize error."""
        super().__init__()

        self.name = name
        self.area = area


def _is_device_class(
    state: State,
    entity: entity_registry.RegistryEntry | None,
    device_classes: Collection[str],
) -> bool:
    """Return true if entity device class matches."""
    # Try entity first
    if (entity is not None) and (entity.device_class is not None):
        # Entity device class can be None or blank as "unset"
        if entity.device_class in device_classes:
            return True

    # Fall back to state attribute
    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    return (device_class is not None) and (device_class in device_classes)


def _has_name(
    state: State, entity: entity_registry.RegistryEntry | None, name: str
) -> bool:
    """Return true if entity name or alias matches."""
    if name in (state.entity_id, state.name.casefold()):
        return True

    # Check name/aliases
    if (entity is None) or (not entity.aliases):
        return False

    return any(name == alias.casefold() for alias in entity.aliases)


def _find_area(
    id_or_name: str, areas: area_registry.AreaRegistry
) -> area_registry.AreaEntry | None:
    """Find an area by id or name, checking aliases too."""
    area = areas.async_get_area(id_or_name) or areas.async_get_area_by_name(id_or_name)
    if area is not None:
        return area

    # Check area aliases
    for maybe_area in areas.areas.values():
        if not maybe_area.aliases:
            continue

        for area_alias in maybe_area.aliases:
            if id_or_name == area_alias.casefold():
                return maybe_area

    return None


def _find_floor(
    id_or_name: str, floors: floor_registry.FloorRegistry
) -> floor_registry.FloorEntry | None:
    """Find an floor by id or name, checking aliases too."""
    floor = floors.async_get_floor(id_or_name) or floors.async_get_floor_by_name(
        id_or_name
    )
    if floor is not None:
        return floor

    # Check floor aliases
    for maybe_floor in floors.floors.values():
        if not maybe_floor.aliases:
            continue

        for floor_alias in maybe_floor.aliases:
            if id_or_name == floor_alias.casefold():
                return maybe_floor

    return None


def _filter_by_areas(
    states_and_entities: list[tuple[State, entity_registry.RegistryEntry | None]],
    areas: Iterable[area_registry.AreaEntry],
    devices: device_registry.DeviceRegistry,
) -> Iterable[tuple[State, entity_registry.RegistryEntry | None]]:
    """Filter state/entity pairs by an area."""
    filter_area_ids: set[str | None] = {a.id for a in areas}
    entity_area_ids: dict[str, str | None] = {}
    for _state, entity in states_and_entities:
        if entity is None:
            continue

        if entity.area_id:
            # Use entity's area id first
            entity_area_ids[entity.id] = entity.area_id
        elif entity.device_id:
            # Fall back to device area if not set on entity
            device = devices.async_get(entity.device_id)
            if device is not None:
                entity_area_ids[entity.id] = device.area_id

    for state, entity in states_and_entities:
        if (entity is not None) and (entity_area_ids.get(entity.id) in filter_area_ids):
            yield (state, entity)


@callback
@bind_hass
def async_match_states(
    hass: HomeAssistant,
    name: str | None = None,
    area_name: str | None = None,
    area: area_registry.AreaEntry | None = None,
    floor_name: str | None = None,
    floor: floor_registry.FloorEntry | None = None,
    domains: Collection[str] | None = None,
    device_classes: Collection[str] | None = None,
    states: Iterable[State] | None = None,
    entities: entity_registry.EntityRegistry | None = None,
    areas: area_registry.AreaRegistry | None = None,
    floors: floor_registry.FloorRegistry | None = None,
    devices: device_registry.DeviceRegistry | None = None,
    assistant: str | None = None,
) -> Iterable[State]:
    """Find states that match the constraints."""
    if states is None:
        # All states
        states = hass.states.async_all()

    if entities is None:
        entities = entity_registry.async_get(hass)

    if devices is None:
        devices = device_registry.async_get(hass)

    if areas is None:
        areas = area_registry.async_get(hass)

    if floors is None:
        floors = floor_registry.async_get(hass)

    # Gather entities
    states_and_entities: list[tuple[State, entity_registry.RegistryEntry | None]] = []
    for state in states:
        entity = entities.async_get(state.entity_id)
        if (entity is not None) and entity.entity_category:
            # Skip diagnostic entities
            continue

        states_and_entities.append((state, entity))

    # Filter by domain and device class
    if domains:
        states_and_entities = [
            (state, entity)
            for state, entity in states_and_entities
            if state.domain in domains
        ]

    if device_classes:
        # Check device class in state attribute and in entity entry (if available)
        states_and_entities = [
            (state, entity)
            for state, entity in states_and_entities
            if _is_device_class(state, entity, device_classes)
        ]

    filter_areas: list[area_registry.AreaEntry] = []

    if (floor is None) and (floor_name is not None):
        # Look up floor by name
        floor = _find_floor(floor_name, floors)
        if floor is None:
            _LOGGER.warning("Floor not found: %s", floor_name)
            return

    if floor is not None:
        filter_areas = [
            a for a in areas.async_list_areas() if a.floor_id == floor.floor_id
        ]

    if (area is None) and (area_name is not None):
        # Look up area by name
        area = _find_area(area_name, areas)
        if area is None:
            _LOGGER.warning("Area not found: %s", area_name)
            return

    if area is not None:
        filter_areas = [area]

    if filter_areas:
        # Filter by states/entities by area
        states_and_entities = list(
            _filter_by_areas(states_and_entities, filter_areas, devices)
        )

    if assistant is not None:
        # Filter by exposure
        states_and_entities = [
            (state, entity)
            for state, entity in states_and_entities
            if async_should_expose(hass, assistant, state.entity_id)
        ]

    if name is not None:
        # Filter by name
        name = name.casefold()

        # Check states
        for state, entity in states_and_entities:
            if _has_name(state, entity, name):
                yield state
    else:
        # Not filtered by name
        for state, _entity in states_and_entities:
            yield state


@callback
def async_test_feature(state: State, feature: int, feature_name: str) -> None:
    """Test if state supports a feature."""
    if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & feature == 0:
        raise IntentHandleError(f"Entity {state.name} does not support {feature_name}")


class IntentHandler:
    """Intent handler registration."""

    intent_type: str | None = None
    slot_schema: vol.Schema | None = None
    platforms: Iterable[str] | None = []

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


class DynamicServiceIntentHandler(IntentHandler):
    """Service Intent handler registration (dynamic).

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {
        vol.Any("name", "area", "floor"): cv.string,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("device_class"): vol.All(cv.ensure_list, [cv.string]),
    }

    # We use a small timeout in service calls to (hopefully) pass validation
    # checks, but not try to wait for the call to fully complete.
    service_timeout: float = 0.2

    def __init__(
        self,
        intent_type: str,
        speech: str | None = None,
        extra_slots: dict[str, vol.Schema] | None = None,
    ) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.speech = speech
        self.extra_slots = extra_slots

    @cached_property
    def _slot_schema(self) -> vol.Schema:
        """Create validation schema for slots (with extra required slots)."""
        if self.slot_schema is None:
            raise ValueError("Slot schema is not defined")

        if self.extra_slots:
            slot_schema = {
                **self.slot_schema,
                **{
                    vol.Required(key): schema
                    for key, schema in self.extra_slots.items()
                },
            }
        else:
            slot_schema = self.slot_schema

        return vol.Schema(
            {
                key: SLOT_SCHEMA.extend({"value": validator})
                for key, validator in slot_schema.items()
            },
            extra=vol.ALLOW_EXTRA,
        )

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

        # Look up area to fail early
        area_slot = slots.get("area", {})
        area_id = area_slot.get("value")
        area_name = area_slot.get("text")
        area: area_registry.AreaEntry | None = None
        if area_id is not None:
            areas = area_registry.async_get(hass)
            area = areas.async_get_area(area_id)
            if area is None:
                raise IntentHandleError(f"No area named {area_name}")

        # Look up floor to fail early
        floor_slot = slots.get("floor", {})
        floor_id = floor_slot.get("value")
        floor_name = floor_slot.get("text")
        floor: floor_registry.FloorEntry | None = None
        if floor_id is not None:
            floors = floor_registry.async_get(hass)
            floor = floors.async_get_floor(floor_id)
            if floor is None:
                raise IntentHandleError(f"No floor named {floor_name}")

        # Optional domain/device class filters.
        # Convert to sets for speed.
        domains: set[str] | None = None
        device_classes: set[str] | None = None

        if "domain" in slots:
            domains = set(slots["domain"]["value"])

        if "device_class" in slots:
            device_classes = set(slots["device_class"]["value"])

        states = list(
            async_match_states(
                hass,
                name=entity_name,
                area=area,
                floor=floor,
                domains=domains,
                device_classes=device_classes,
                assistant=intent_obj.assistant,
            )
        )

        if not states:
            # No states matched constraints
            raise NoStatesMatchedError(
                name=entity_text or entity_name,
                area=area_name or area_id,
                floor=floor_name or floor_id,
                domains=domains,
                device_classes=device_classes,
            )

        if entity_name and (len(states) > 1):
            # Multiple entities matched for the same name
            raise DuplicateNamesMatchedError(
                name=entity_text or entity_name,
                area=area_name or area_id,
            )

        # Update intent slots to include any transformations done by the schemas
        intent_obj.slots = slots

        response = await self.async_handle_states(intent_obj, states, area)

        # Make the matched states available in the response
        response.async_set_states(matched_states=states, unmatched_states=[])

        return response

    async def async_handle_states(
        self,
        intent_obj: Intent,
        states: list[State],
        area: area_registry.AreaEntry | None = None,
    ) -> IntentResponse:
        """Complete action on matched entity states."""
        assert states, "No states"
        hass = intent_obj.hass
        success_results: list[IntentResponseTarget] = []
        response = intent_obj.create_response()

        if area is not None:
            success_results.append(
                IntentResponseTarget(
                    type=IntentResponseTargetType.AREA, name=area.name, id=area.id
                )
            )
            speech_name = area.name
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
            except Exception:  # pylint: disable=broad-except
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
        if self.extra_slots:
            service_data.update(
                {key: intent_obj.slots[key]["value"] for key in self.extra_slots}
            )

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
        extra_slots: dict[str, vol.Schema] | None = None,
    ) -> None:
        """Create service handler."""
        super().__init__(intent_type, speech=speech, extra_slots=extra_slots)
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
