"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/

"""
import asyncio
import enum
import logging

from homeassistant.core import callback
from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.helpers import intent
from homeassistant.components import http

from .const import DOMAIN, SYN_RESOLUTION_MATCH

INTENTS_API_ENDPOINT = '/api/alexa'

_LOGGER = logging.getLogger(__name__)


class SpeechType(enum.Enum):
    """The Alexa speech types."""

    plaintext = "PlainText"
    ssml = "SSML"


SPEECH_MAPPINGS = {
    'plain': SpeechType.plaintext,
    'ssml': SpeechType.ssml,
}


class CardType(enum.Enum):
    """The Alexa card types."""

    simple = "Simple"
    link_account = "LinkAccount"


@callback
def async_setup(hass):
    """Activate Alexa component."""
    hass.http.register_view(AlexaIntentsView)


class AlexaIntentsView(http.HomeAssistantView):
    """Handle Alexa requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:alexa'

    @asyncio.coroutine
    def post(self, request):
        """Handle Alexa."""
        hass = request.app['hass']
        data = yield from request.json()

        _LOGGER.debug('Received Alexa request: %s', data)

        req = data.get('request')

        if req is None:
            _LOGGER.error('Received invalid data from Alexa: %s', data)
            return self.json_message('Expected request value not received',
                                     HTTP_BAD_REQUEST)

        req_type = req['type']

        if req_type == 'SessionEndedRequest':
            return None

        alexa_intent_info = req.get('intent')
        alexa_response = AlexaResponse(hass, alexa_intent_info)

        if req_type != 'IntentRequest' and req_type != 'LaunchRequest':
            _LOGGER.warning('Received unsupported request: %s', req_type)
            return self.json_message(
                'Received unsupported request: {}'.format(req_type),
                HTTP_BAD_REQUEST)

        if req_type == 'LaunchRequest':
            intent_name = data.get('session', {})       \
                              .get('application', {})   \
                              .get('applicationId')
        else:
            intent_name = alexa_intent_info['name']

        try:
            intent_response = yield from intent.async_handle(
                hass, DOMAIN, intent_name,
                {key: {'value': value} for key, value
                 in alexa_response.variables.items()})
        except intent.UnknownIntent as err:
            _LOGGER.warning('Received unknown intent %s', intent_name)
            alexa_response.add_speech(
                SpeechType.plaintext,
                "This intent is not yet configured within Home Assistant.")
            return self.json(alexa_response)

        except intent.InvalidSlotInfo as err:
            _LOGGER.error('Received invalid slot data from Alexa: %s', err)
            return self.json_message('Invalid slot data received',
                                     HTTP_BAD_REQUEST)
        except intent.IntentError:
            _LOGGER.exception('Error handling request for %s', intent_name)
            return self.json_message('Error handling intent', HTTP_BAD_REQUEST)

        for intent_speech, alexa_speech in SPEECH_MAPPINGS.items():
            if intent_speech in intent_response.speech:
                alexa_response.add_speech(
                    alexa_speech,
                    intent_response.speech[intent_speech]['speech'])
                break

        if 'simple' in intent_response.card:
            alexa_response.add_card(
                CardType.simple, intent_response.card['simple']['title'],
                intent_response.card['simple']['content'])

        return self.json(alexa_response)


def resolve_slot_synonyms(key, request):
    """Check slot request for synonym resolutions."""
    # Default to the spoken slot value if more than one or none are found. For
    # reference to the request object structure, see the Alexa docs:
    # https://tinyurl.com/ybvm7jhs
    resolved_value = request['value']

    if ('resolutions' in request and
            'resolutionsPerAuthority' in request['resolutions'] and
            len(request['resolutions']['resolutionsPerAuthority']) >= 1):

        # Extract all of the possible values from each authority with a
        # successful match
        possible_values = []

        for entry in request['resolutions']['resolutionsPerAuthority']:
            if entry['status']['code'] != SYN_RESOLUTION_MATCH:
                continue

            possible_values.extend([item['value']['name']
                                    for item
                                    in entry['values']])

        # If there is only one match use the resolved value, otherwise the
        # resolution cannot be determined, so use the spoken slot value
        if len(possible_values) == 1:
            resolved_value = possible_values[0]
        else:
            _LOGGER.debug(
                'Found multiple synonym resolutions for slot value: {%s: %s}',
                key,
                request['value']
            )

    return resolved_value


class AlexaResponse(object):
    """Help generating the response for Alexa."""

    def __init__(self, hass, intent_info):
        """Initialize the response."""
        self.hass = hass
        self.speech = None
        self.card = None
        self.reprompt = None
        self.session_attributes = {}
        self.should_end_session = True
        self.variables = {}

        # Intent is None if request was a LaunchRequest or SessionEndedRequest
        if intent_info is not None:
            for key, value in intent_info.get('slots', {}).items():
                # Only include slots with values
                if 'value' not in value:
                    continue

                _key = key.replace('.', '_')

                self.variables[_key] = resolve_slot_synonyms(key, value)

    def add_card(self, card_type, title, content):
        """Add a card to the response."""
        assert self.card is None

        card = {
            "type": card_type.value
        }

        if card_type == CardType.link_account:
            self.card = card
            return

        card["title"] = title
        card["content"] = content
        self.card = card

    def add_speech(self, speech_type, text):
        """Add speech to the response."""
        assert self.speech is None

        key = 'ssml' if speech_type == SpeechType.ssml else 'text'

        self.speech = {
            'type': speech_type.value,
            key: text
        }

    def add_reprompt(self, speech_type, text):
        """Add reprompt if user does not answer."""
        assert self.reprompt is None

        key = 'ssml' if speech_type == SpeechType.ssml else 'text'

        self.reprompt = {
            'type': speech_type.value,
            key: text.async_render(self.variables)
        }

    def as_dict(self):
        """Return response in an Alexa valid dict."""
        response = {
            'shouldEndSession': self.should_end_session
        }

        if self.card is not None:
            response['card'] = self.card

        if self.speech is not None:
            response['outputSpeech'] = self.speech

        if self.reprompt is not None:
            response['reprompt'] = {
                'outputSpeech': self.reprompt
            }

        return {
            'version': '1.0',
            'sessionAttributes': self.session_attributes,
            'response': response,
        }
