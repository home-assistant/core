"""Module to coordinate user intentions."""
import asyncio
import logging
import re

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.const import ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

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
def async_register(hass, handler):
    """Register an intent with Home Assistant."""
    intents = hass.data.get(DATA_KEY)
    if intents is None:
        intents = hass.data[DATA_KEY] = {}

    if handler.intent_type in intents:
        _LOGGER.warning('Intent %s is being overwritten by %s.',
                        handler.intent_type, handler)

    intents[handler.intent_type] = handler


@asyncio.coroutine
@bind_hass
def async_handle(hass, platform, intent_type, slots=None, text_input=None):
    """Handle an intent."""
    handler = hass.data.get(DATA_KEY, {}).get(intent_type)

    if handler is None:
        raise UnknownIntent('Unknown intent {}'.format(intent_type))

    intent = Intent(hass, platform, intent_type, slots or {}, text_input)

    try:
        _LOGGER.info("Triggering intent handler %s", handler)
        result = yield from handler.async_handle(intent)
        return result
    except vol.Invalid as err:
        raise InvalidSlotInfo(
            'Received invalid slot info for {}'.format(intent_type)) from err
    except Exception as err:
        raise IntentHandleError(
            'Error handling {}'.format(intent_type)) from err


class IntentError(HomeAssistantError):
    """Base class for intent related errors."""

    pass


class UnknownIntent(IntentError):
    """When the intent is not registered."""

    pass


class InvalidSlotInfo(IntentError):
    """When the slot data is invalid."""

    pass


class IntentHandleError(IntentError):
    """Error while handling intent."""

    pass


class IntentHandler:
    """Intent handler registration."""

    intent_type = None
    slot_schema = None
    _slot_schema = None
    platforms = []

    @callback
    def async_can_handle(self, intent_obj):
        """Test if an intent can be handled."""
        return self.platforms is None or intent_obj.platform in self.platforms

    @callback
    def async_validate_slots(self, slots):
        """Validate slot information."""
        if self.slot_schema is None:
            return slots

        if self._slot_schema is None:
            self._slot_schema = vol.Schema({
                key: SLOT_SCHEMA.extend({'value': validator})
                for key, validator in self.slot_schema.items()})

        return self._slot_schema(slots)

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        raise NotImplementedError()

    def __repr__(self):
        """Represent a string of an intent handler."""
        return '<{} - {}>'.format(self.__class__.__name__, self.intent_type)


def fuzzymatch(name, entities):
    """Fuzzy matching function."""
    matches = []
    pattern = '.*?'.join(name)
    regex = re.compile(pattern, re.IGNORECASE)
    for entity_id, entity_name in entities.items():
        match = regex.search(entity_name)
        if match:
            matches.append((len(match.group()), match.start(), entity_id))
    return [x for _, _, x in sorted(matches)]


class ServiceIntentHandler(IntentHandler):
    """Service Intent handler registration.

    Service specific intent handler that calls a service by name/entity_id.
    """

    slot_schema = {
        'name': cv.string,
    }

    def __init__(self, intent_type, domain, service, speech):
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.domain = domain
        self.service = service
        self.speech = speech

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        response = intent_obj.create_response()

        name = slots['name']['value']
        entities = {state.entity_id: state.name for state
                    in hass.states.async_all()}

        matches = fuzzymatch(name, entities)
        entity_id = matches[0] if matches else None
        _LOGGER.debug("%s matched entity: %s", name, entity_id)

        response = intent_obj.create_response()
        if not entity_id:
            response.async_set_speech(
                "Could not find entity id matching {}.".format(name))
            _LOGGER.error("Could not find entity id matching %s", name)
            return response

        yield from hass.services.async_call(
            self.domain, self.service, {
                ATTR_ENTITY_ID: entity_id
            })

        response.async_set_speech(
            self.speech.format(name))
        return response


class Intent:
    """Hold the intent."""

    __slots__ = ['hass', 'platform', 'intent_type', 'slots', 'text_input']

    def __init__(self, hass, platform, intent_type, slots, text_input):
        """Initialize an intent."""
        self.hass = hass
        self.platform = platform
        self.intent_type = intent_type
        self.slots = slots
        self.text_input = text_input

    @callback
    def create_response(self):
        """Create a response."""
        return IntentResponse(self)


class IntentResponse:
    """Response to an intent."""

    def __init__(self, intent=None):
        """Initialize an IntentResponse."""
        self.intent = intent
        self.speech = {}
        self.card = {}

    @callback
    def async_set_speech(self, speech, speech_type='plain', extra_data=None):
        """Set speech response."""
        self.speech[speech_type] = {
            'speech': speech,
            'extra_data': extra_data,
        }

    @callback
    def async_set_card(self, title, content, card_type='simple'):
        """Set speech response."""
        self.card[card_type] = {
            'title': title,
            'content': content,
        }

    @callback
    def as_dict(self):
        """Return a dictionary representation of an intent response."""
        return {
            'speech': self.speech,
            'card': self.card,
        }
