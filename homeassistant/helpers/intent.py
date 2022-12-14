"""Module to coordinate user intentions."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import dataclasses
from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import Any, TypeVar

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass

from . import config_validation as cv

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

    state = _fuzzymatch(name, states, lambda state: state.name)

    if state is None:
        raise IntentHandleError(f"Unable to find an entity called {name}")

    return state


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


def _fuzzymatch(name: str, items: Iterable[_T], key: Callable[[_T], str]) -> _T | None:
    """Fuzzy matching function."""
    matches = []
    pattern = ".*?".join(name)
    regex = re.compile(pattern, re.IGNORECASE)
    for idx, item in enumerate(items):
        if match := regex.search(key(item)):
            # Add key length so we prefer shorter keys with the same group and start.
            # Add index so we pick first match in case same group, start, and key length.
            matches.append(
                (len(match.group()), match.start(), len(key(item)), idx, item)
            )

    return sorted(matches)[0][4] if matches else None


class ServiceIntentHandler(IntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {vol.Required("name"): cv.string}

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
