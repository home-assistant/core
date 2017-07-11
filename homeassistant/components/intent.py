"""Module to coordinate user intentions."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError


DOMAIN = 'intent'
_LOGGER = logging.getLogger(__name__)

SLOT_SCHEMA = vol.Schema({
    vol.Optional('type'): str,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup intent."""
    hass.intent = IntentRegistry(hass)
    return True


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
    platforms = None

    @callback
    def async_can_handle(self, intent):
        """Test if an intent can be handled."""
        return self.platforms is None or intent.platform in self.platforms

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
    def async_handle(self, intent):
        """Handle the intent."""
        raise NotImplementedError()

    def __repr__(self):
        """String representation of intent handler."""
        return '<{} - {}>'.format(self.__class__.__name__, self.intent_type)


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

    def __init__(self, intent):
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


class IntentRegistry:
    """Registry of intent handlers."""

    def __init__(self, hass):
        """Initialize intent registry."""
        self.hass = hass
        self.intents = {}

    @callback
    def async_register(self, handler):
        """Register an intent."""
        if handler.intent_type in self.intents:
            _LOGGER.warning('Intent %s is being overwritten by %s.',
                            handler.intent_type, handler)
            return

        self.intents[handler.intent_type] = handler

    @asyncio.coroutine
    def async_handle(self, platform, intent_type, slots=None, text_input=None):
        """Handle an intent."""
        handler = self.intents.get(intent_type)

        if handler is None:
            raise UnknownIntent()

        intent = Intent(self.hass, platform, intent_type, slots or {},
                        text_input)

        try:
            result = yield from handler.async_handle(intent)
            return result
        except vol.Invalid as err:
            raise InvalidSlotInfo from err
        except Exception as err:
            raise IntentHandleError from err
