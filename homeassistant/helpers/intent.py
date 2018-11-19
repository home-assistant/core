"""Module to coordinate user intentions."""
import logging
import re
from typing import Any, Callable, Dict, Iterable, Optional

import voluptuous as vol

from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import callback, State, T
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass
from homeassistant.const import ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)
_SlotsType = Dict[str, Any]

INTENT_TURN_OFF = 'HassTurnOff'
INTENT_TURN_ON = 'HassTurnOn'
INTENT_TOGGLE = 'HassToggle'

SLOT_SCHEMA = vol.Schema({
}, extra=vol.ALLOW_EXTRA)

DATA_KEY = 'intent'

SPEECH_TYPE_PLAIN = 'plain'
SPEECH_TYPE_SSML = 'ssml'


@callback
@bind_hass
def async_register(hass: HomeAssistantType, handler: 'IntentHandler') -> None:
    """Register an intent with Home Assistant."""
    intents = hass.data.get(DATA_KEY)
    if intents is None:
        intents = hass.data[DATA_KEY] = {}

    assert handler.intent_type is not None, 'intent_type cannot be None'

    if handler.intent_type in intents:
        _LOGGER.warning('Intent %s is being overwritten by %s.',
                        handler.intent_type, handler)

    intents[handler.intent_type] = handler


@bind_hass
async def async_handle(hass: HomeAssistantType, platform: str,
                       intent_type: str, slots: Optional[_SlotsType] = None,
                       text_input: Optional[str] = None) -> 'IntentResponse':
    """Handle an intent."""
    handler = \
        hass.data.get(DATA_KEY, {}).get(intent_type)  # type: IntentHandler

    if handler is None:
        raise UnknownIntent('Unknown intent {}'.format(intent_type))

    intent = Intent(hass, platform, intent_type, slots or {}, text_input)

    try:
        _LOGGER.info("Triggering intent handler %s", handler)
        result = await handler.async_handle(intent)
        return result
    except vol.Invalid as err:
        _LOGGER.warning('Received invalid slot info for %s: %s',
                        intent_type, err)
        raise InvalidSlotInfo(
            'Received invalid slot info for {}'.format(intent_type)) from err
    # https://github.com/PyCQA/pylint/issues/2284
    except IntentHandleError:  # pylint: disable=try-except-raise
        raise
    except Exception as err:
        raise IntentUnexpectedError(
            'Error handling {}'.format(intent_type)) from err


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
def async_match_state(hass: HomeAssistantType, name: str,
                      states: Optional[Iterable[State]] = None) -> State:
    """Find a state that matches the name."""
    if states is None:
        states = hass.states.async_all()

    state = _fuzzymatch(name, states, lambda state: state.name)

    if state is None:
        raise IntentHandleError(
            'Unable to find an entity called {}'.format(name))

    return state


@callback
def async_test_feature(state: State, feature: int, feature_name: str) -> None:
    """Test is state supports a feature."""
    if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & feature == 0:
        raise IntentHandleError(
            'Entity {} does not support {}'.format(
                state.name, feature_name))


class IntentHandler:
    """Intent handler registration."""

    intent_type = None  # type: Optional[str]
    slot_schema = None  # type: Optional[vol.Schema]
    _slot_schema = None
    platforms = []  # type: Optional[Iterable[str]]

    @callback
    def async_can_handle(self, intent_obj: 'Intent') -> bool:
        """Test if an intent can be handled."""
        return self.platforms is None or intent_obj.platform in self.platforms

    @callback
    def async_validate_slots(self, slots: _SlotsType) -> _SlotsType:
        """Validate slot information."""
        if self.slot_schema is None:
            return slots

        if self._slot_schema is None:
            self._slot_schema = vol.Schema({
                key: SLOT_SCHEMA.extend({'value': validator})
                for key, validator in self.slot_schema.items()},
                                           extra=vol.ALLOW_EXTRA)

        return self._slot_schema(slots)  # type: ignore

    async def async_handle(self, intent_obj: 'Intent') -> 'IntentResponse':
        """Handle the intent."""
        raise NotImplementedError()

    def __repr__(self) -> str:
        """Represent a string of an intent handler."""
        return '<{} - {}>'.format(self.__class__.__name__, self.intent_type)


def _fuzzymatch(name: str, items: Iterable[T], key: Callable[[T], str]) \
        -> Optional[T]:
    """Fuzzy matching function."""
    matches = []
    pattern = '.*?'.join(name)
    regex = re.compile(pattern, re.IGNORECASE)
    for idx, item in enumerate(items):
        match = regex.search(key(item))
        if match:
            # Add index so we pick first match in case same group and start
            matches.append((len(match.group()), match.start(), idx, item))

    return sorted(matches)[0][3] if matches else None


class ServiceIntentHandler(IntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {
        vol.Required('name'): cv.string,
    }

    def __init__(self, intent_type: str, domain: str, service: str,
                 speech: str) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.domain = domain
        self.service = service
        self.speech = speech

    async def async_handle(self, intent_obj: 'Intent') -> 'IntentResponse':
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        state = async_match_state(hass, slots['name']['value'])

        await hass.services.async_call(self.domain, self.service, {
            ATTR_ENTITY_ID: state.entity_id
        })

        response = intent_obj.create_response()
        response.async_set_speech(self.speech.format(state.name))
        return response


class Intent:
    """Hold the intent."""

    __slots__ = ['hass', 'platform', 'intent_type', 'slots', 'text_input']

    def __init__(self, hass: HomeAssistantType, platform: str,
                 intent_type: str, slots: _SlotsType,
                 text_input: Optional[str]) -> None:
        """Initialize an intent."""
        self.hass = hass
        self.platform = platform
        self.intent_type = intent_type
        self.slots = slots
        self.text_input = text_input

    @callback
    def create_response(self) -> 'IntentResponse':
        """Create a response."""
        return IntentResponse(self)


class IntentResponse:
    """Response to an intent."""

    def __init__(self, intent: Optional[Intent] = None) -> None:
        """Initialize an IntentResponse."""
        self.intent = intent
        self.speech = {}  # type: Dict[str, Dict[str, Any]]
        self.card = {}  # type: Dict[str, Dict[str, str]]

    @callback
    def async_set_speech(self, speech: str, speech_type: str = 'plain',
                         extra_data: Optional[Any] = None) -> None:
        """Set speech response."""
        self.speech[speech_type] = {
            'speech': speech,
            'extra_data': extra_data,
        }

    @callback
    def async_set_card(self, title: str, content: str,
                       card_type: str = 'simple') -> None:
        """Set speech response."""
        self.card[card_type] = {
            'title': title,
            'content': content,
        }

    @callback
    def as_dict(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Return a dictionary representation of an intent response."""
        return {
            'speech': self.speech,
            'card': self.card,
        }
