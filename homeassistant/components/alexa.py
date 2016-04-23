"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/
"""
import enum
import logging

from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY
from homeassistant.helpers import template, script

DOMAIN = 'alexa'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)
_CONFIG = {}

API_ENDPOINT = '/api/alexa'

CONF_INTENTS = 'intents'
CONF_CARD = 'card'
CONF_SPEECH = 'speech'
CONF_ACTION = 'action'


def setup(hass, config):
    """Activate Alexa component."""
    intents = config[DOMAIN].get(CONF_INTENTS, {})

    for name, intent in intents.items():
        if CONF_ACTION in intent:
            intent[CONF_ACTION] = script.Script(hass, intent[CONF_ACTION],
                                                "Alexa intent {}".format(name))

    _CONFIG.update(intents)

    hass.http.register_path('POST', API_ENDPOINT, _handle_alexa, True)

    return True


def _handle_alexa(handler, path_match, data):
    """Handle Alexa."""
    _LOGGER.debug('Received Alexa request: %s', data)

    req = data.get('request')

    if req is None:
        _LOGGER.error('Received invalid data from Alexa: %s', data)
        handler.write_json_message(
            "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
        return

    req_type = req['type']

    if req_type == 'SessionEndedRequest':
        handler.send_response(HTTP_OK)
        handler.end_headers()
        return

    intent = req.get('intent')
    response = AlexaResponse(handler.server.hass, intent)

    if req_type == 'LaunchRequest':
        response.add_speech(
            SpeechType.plaintext,
            "Hello, and welcome to the future. How may I help?")
        handler.write_json(response.as_dict())
        return

    if req_type != 'IntentRequest':
        _LOGGER.warning('Received unsupported request: %s', req_type)
        return

    intent_name = intent['name']
    config = _CONFIG.get(intent_name)

    if config is None:
        _LOGGER.warning('Received unknown intent %s', intent_name)
        response.add_speech(
            SpeechType.plaintext,
            "This intent is not yet configured within Home Assistant.")
        handler.write_json(response.as_dict())
        return

    speech = config.get(CONF_SPEECH)
    card = config.get(CONF_CARD)
    action = config.get(CONF_ACTION)

    # pylint: disable=unsubscriptable-object
    if speech is not None:
        response.add_speech(SpeechType[speech['type']], speech['text'])

    if card is not None:
        response.add_card(CardType[card['type']], card['title'],
                          card['content'])

    if action is not None:
        action.run(response.variables)

    handler.write_json(response.as_dict())


class SpeechType(enum.Enum):
    """The Alexa speech types."""

    plaintext = "PlainText"
    ssml = "SSML"


class CardType(enum.Enum):
    """The Alexa card types."""

    simple = "Simple"
    link_account = "LinkAccount"


class AlexaResponse(object):
    """Help generating the response for Alexa."""

    def __init__(self, hass, intent=None):
        """Initialize the response."""
        self.hass = hass
        self.speech = None
        self.card = None
        self.reprompt = None
        self.session_attributes = {}
        self.should_end_session = True
        if intent is not None and 'slots' in intent:
            self.variables = {key: value['value'] for key, value
                              in intent['slots'].items() if 'value' in value}
        else:
            self.variables = {}

    def add_card(self, card_type, title, content):
        """Add a card to the response."""
        assert self.card is None

        card = {
            "type": card_type.value
        }

        if card_type == CardType.link_account:
            self.card = card
            return

        card["title"] = self._render(title),
        card["content"] = self._render(content)
        self.card = card

    def add_speech(self, speech_type, text):
        """Add speech to the response."""
        assert self.speech is None

        key = 'ssml' if speech_type == SpeechType.ssml else 'text'

        self.speech = {
            'type': speech_type.value,
            key: self._render(text)
        }

    def add_reprompt(self, speech_type, text):
        """Add reprompt if user does not answer."""
        assert self.reprompt is None

        key = 'ssml' if speech_type == SpeechType.ssml else 'text'

        self.reprompt = {
            'type': speech_type.value,
            key: self._render(text)
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

    def _render(self, template_string):
        """Render a response, adding data from intent if available."""
        return template.render(self.hass, template_string, self.variables)
