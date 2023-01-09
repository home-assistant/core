"""Module to coordinate user intentions."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, TypeVar

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass

from . import area_registry, config_validation as cv, entity_registry

_LOGGER = logging.getLogger(__name__)
_SlotsType = dict[str, Any]
_T = TypeVar("_T")

INTENT_TURN_OFF = "HassTurnOff"
INTENT_TURN_ON = "HassTurnOn"
INTENT_TOGGLE = "HassToggle"

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


@bind_hass
async def async_handle(
    hass: HomeAssistant,
    platform: str,
    intent_type: str,
    slots: _SlotsType | None = None,
    text_input: str | None = None,
    context: Context | None = None,
    language: str | None = None,
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
        hass, platform, intent_type, slots or {}, text_input, context, language
    )

    try:
        _LOGGER.info("Triggering intent handler %s", handler)
        result = await handler.async_handle(intent)
        return result
    except vol.Invalid as err:
        _LOGGER.warning("Received invalid slot info for %s: %s", intent_type, err)
        raise InvalidSlotInfo(f"Received invalid slot info for {intent_type}") from err
    except IntentHandleError:
        raise
    except Exception as err:
        raise IntentUnexpectedError(f"Error handling {intent_type}") from err


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


@callback
@bind_hass
def async_match_state(
    hass: HomeAssistant, name: str, states: Iterable[State] | None = None
) -> State:
    """Find a state that matches the name."""
    if states is None:
        states = hass.states.async_all()

    name = name.casefold()
    state: State | None = None
    registry = entity_registry.async_get(hass)

    for maybe_state in states:
        # Check entity id and name
        if name in (maybe_state.entity_id, maybe_state.name.casefold()):
            state = maybe_state
        else:
            # Check aliases
            entry = registry.async_get(maybe_state.entity_id)
            if (entry is not None) and entry.aliases:
                for alias in entry.aliases:
                    if name == alias.casefold():
                        state = maybe_state
                        break

        if state is not None:
            break

    if state is None:
        raise IntentHandleError(f"Unable to find an entity called {name}")

    return state


@callback
@bind_hass
def async_match_area(
    hass: HomeAssistant, area_name: str
) -> area_registry.AreaEntry | None:
    """Find an area that matches the name."""
    registry = area_registry.async_get(hass)
    return registry.async_get_area(area_name) or registry.async_get_area_by_name(
        area_name
    )


@callback
def async_test_feature(state: State, feature: int, feature_name: str) -> None:
    """Test if state supports a feature."""
    if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & feature == 0:
        raise IntentHandleError(f"Entity {state.name} does not support {feature_name}")


class IntentHandler:
    """Intent handler registration."""

    intent_type: str | None = None
    slot_schema: vol.Schema | None = None
    _slot_schema: vol.Schema | None = None
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

        if self._slot_schema is None:
            self._slot_schema = vol.Schema(
                {
                    key: SLOT_SCHEMA.extend({"value": validator})
                    for key, validator in self.slot_schema.items()
                },
                extra=vol.ALLOW_EXTRA,
            )

        return self._slot_schema(slots)  # type: ignore[no-any-return]

    async def async_handle(self, intent_obj: Intent) -> IntentResponse:
        """Handle the intent."""
        raise NotImplementedError()

    def __repr__(self) -> str:
        """Represent a string of an intent handler."""
        return f"<{self.__class__.__name__} - {self.intent_type}>"


class ServiceIntentHandler(IntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {
        vol.Any("name", "area"): cv.string,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("device_class"): vol.All(cv.ensure_list, [cv.string]),
    }

    def __init__(
        self, intent_type: str, domain: str, service: str, speech: str
    ) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.domain = domain
        self.service = service
        self.speech = speech

    async def async_handle(self, intent_obj: Intent) -> IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        if "area" in slots:
            # Entities in an area
            area_name = slots["area"]["value"]
            area = async_match_area(hass, area_name)
            assert area is not None
            assert area.id is not None

            # Optional domain filter
            domains: set[str] | None = None
            if "domain" in slots:
                domains = set(slots["domain"]["value"])

            # Optional device class filter
            device_classes: set[str] | None = None
            if "device_class" in slots:
                device_classes = set(slots["device_class"]["value"])

            success_results = [
                IntentResponseTarget(
                    type=IntentResponseTargetType.AREA, name=area.name, id=area.id
                )
            ]
            service_coros = []
            registry = entity_registry.async_get(hass)
            for entity_entry in entity_registry.async_entries_for_area(
                registry, area.id
            ):
                if entity_entry.entity_category:
                    # Skip diagnostic entities
                    continue

                if domains and (entity_entry.domain not in domains):
                    # Skip entity not in the domain
                    continue

                if device_classes and (entity_entry.device_class not in device_classes):
                    # Skip entity with wrong device class
                    continue

                service_coros.append(
                    hass.services.async_call(
                        self.domain,
                        self.service,
                        {ATTR_ENTITY_ID: entity_entry.entity_id},
                        context=intent_obj.context,
                    )
                )

                state = hass.states.get(entity_entry.entity_id)
                assert state is not None

                success_results.append(
                    IntentResponseTarget(
                        type=IntentResponseTargetType.ENTITY,
                        name=state.name,
                        id=entity_entry.entity_id,
                    ),
                )

            if not service_coros:
                raise IntentHandleError("No entities matched")

            # Handle service calls in parallel.
            # We will need to handle partial failures here.
            await asyncio.gather(*service_coros)

            response = intent_obj.create_response()
            response.async_set_speech(self.speech.format(area.name))
            response.async_set_results(
                success_results=success_results,
            )
        else:
            # Single entity
            state = async_match_state(hass, slots["name"]["value"])

            await hass.services.async_call(
                self.domain,
                self.service,
                {ATTR_ENTITY_ID: state.entity_id},
                context=intent_obj.context,
            )

            response = intent_obj.create_response()
            response.async_set_speech(self.speech.format(state.name))
            response.async_set_results(
                success_results=[
                    IntentResponseTarget(
                        type=IntentResponseTargetType.ENTITY,
                        name=state.name,
                        id=state.entity_id,
                    ),
                ],
            )

        return response


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


@dataclass
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
