"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/
"""
import asyncio
import copy
import enum
import logging
import uuid
from datetime import datetime

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.helpers import template, script, config_validation as cv
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

INTENTS_API_ENDPOINT = '/api/alexa'
FLASH_BRIEFINGS_API_ENDPOINT = '/api/alexa/flash_briefings/{briefing_id}'

CONF_ACTION = 'action'
CONF_CARD = 'card'
CONF_INTENTS = 'intents'
CONF_SPEECH = 'speech'

CONF_TYPE = 'type'
CONF_TITLE = 'title'
CONF_CONTENT = 'content'
CONF_TEXT = 'text'

CONF_FLASH_BRIEFINGS = 'flash_briefings'
CONF_UID = 'uid'
CONF_TITLE = 'title'
CONF_AUDIO = 'audio'
CONF_TEXT = 'text'
CONF_DISPLAY_URL = 'display_url'

ATTR_UID = 'uid'
ATTR_UPDATE_DATE = 'updateDate'
ATTR_TITLE_TEXT = 'titleText'
ATTR_STREAM_URL = 'streamUrl'
ATTR_MAIN_TEXT = 'mainText'
ATTR_REDIRECTION_URL = 'redirectionURL'

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.0Z'

DOMAIN = 'alexa'
DEPENDENCIES = ['http']


class SpeechType(enum.Enum):
    """The Alexa speech types."""

    plaintext = "PlainText"
    ssml = "SSML"


class CardType(enum.Enum):
    """The Alexa card types."""

    simple = "Simple"
    link_account = "LinkAccount"


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        CONF_INTENTS: {
            cv.string: {
                vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
                vol.Optional(CONF_CARD): {
                    vol.Required(CONF_TYPE): cv.enum(CardType),
                    vol.Required(CONF_TITLE): cv.template,
                    vol.Required(CONF_CONTENT): cv.template,
                },
                vol.Optional(CONF_SPEECH): {
                    vol.Required(CONF_TYPE): cv.enum(SpeechType),
                    vol.Required(CONF_TEXT): cv.template,
                }
            }
        },
        CONF_FLASH_BRIEFINGS: {
            cv.string: vol.All(cv.ensure_list, [{
                vol.Required(CONF_UID, default=str(uuid.uuid4())): cv.string,
                vol.Required(CONF_TITLE): cv.template,
                vol.Optional(CONF_AUDIO): cv.template,
                vol.Required(CONF_TEXT, default=""): cv.template,
                vol.Optional(CONF_DISPLAY_URL): cv.template,
            }]),
        }
    }
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Activate Alexa component."""
    intents = config[DOMAIN].get(CONF_INTENTS, {})
    flash_briefings = config[DOMAIN].get(CONF_FLASH_BRIEFINGS, {})

    hass.http.register_view(AlexaIntentsView(hass, intents))
    hass.http.register_view(AlexaFlashBriefingView(hass, flash_briefings))

    return True


class AlexaIntentsView(HomeAssistantView):
    """Handle Alexa requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:alexa'

    def __init__(self, hass, intents):
        """Initialize Alexa view."""
        super().__init__()

        intents = copy.deepcopy(intents)
        template.attach(hass, intents)

        for name, intent in intents.items():
            if CONF_ACTION in intent:
                intent[CONF_ACTION] = script.Script(
                    hass, intent[CONF_ACTION], "Alexa intent {}".format(name))

        self.intents = intents

    @asyncio.coroutine
    def post(self, request):
        """Handle Alexa."""
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

        intent = req.get('intent')
        response = AlexaResponse(request.app['hass'], intent)

        if req_type == 'LaunchRequest':
            response.add_speech(
                SpeechType.plaintext,
                "Hello, and welcome to the future. How may I help?")
            return self.json(response)

        if req_type != 'IntentRequest':
            _LOGGER.warning('Received unsupported request: %s', req_type)
            return self.json_message(
                'Received unsupported request: {}'.format(req_type),
                HTTP_BAD_REQUEST)

        intent_name = intent['name']
        config = self.intents.get(intent_name)

        if config is None:
            _LOGGER.warning('Received unknown intent %s', intent_name)
            response.add_speech(
                SpeechType.plaintext,
                "This intent is not yet configured within Home Assistant.")
            return self.json(response)

        speech = config.get(CONF_SPEECH)
        card = config.get(CONF_CARD)
        action = config.get(CONF_ACTION)

        if action is not None:
            yield from action.async_run(response.variables)

        # pylint: disable=unsubscriptable-object
        if speech is not None:
            response.add_speech(speech[CONF_TYPE], speech[CONF_TEXT])

        if card is not None:
            response.add_card(card[CONF_TYPE], card[CONF_TITLE],
                              card[CONF_CONTENT])

        return self.json(response)


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
        self.variables = {}
        if intent is not None and 'slots' in intent:
            for key, value in intent['slots'].items():
                if 'value' in value:
                    underscored_key = key.replace('.', '_')
                    self.variables[underscored_key] = value['value']

    def add_card(self, card_type, title, content):
        """Add a card to the response."""
        assert self.card is None

        card = {
            "type": card_type.value
        }

        if card_type == CardType.link_account:
            self.card = card
            return

        card["title"] = title.async_render(self.variables)
        card["content"] = content.async_render(self.variables)
        self.card = card

    def add_speech(self, speech_type, text):
        """Add speech to the response."""
        assert self.speech is None

        key = 'ssml' if speech_type == SpeechType.ssml else 'text'

        if isinstance(text, template.Template):
            text = text.async_render(self.variables)

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


class AlexaFlashBriefingView(HomeAssistantView):
    """Handle Alexa Flash Briefing skill requests."""

    url = FLASH_BRIEFINGS_API_ENDPOINT
    name = 'api:alexa:flash_briefings'

    def __init__(self, hass, flash_briefings):
        """Initialize Alexa view."""
        super().__init__()
        self.flash_briefings = copy.deepcopy(flash_briefings)
        template.attach(hass, self.flash_briefings)

    @callback
    def get(self, request, briefing_id):
        """Handle Alexa Flash Briefing request."""
        _LOGGER.debug('Received Alexa flash briefing request for: %s',
                      briefing_id)

        if self.flash_briefings.get(briefing_id) is None:
            err = 'No configured Alexa flash briefing was found for: %s'
            _LOGGER.error(err, briefing_id)
            return b'', 404

        briefing = []

        for item in self.flash_briefings.get(briefing_id, []):
            output = {}
            if item.get(CONF_TITLE) is not None:
                if isinstance(item.get(CONF_TITLE), template.Template):
                    output[ATTR_TITLE_TEXT] = item[CONF_TITLE].async_render()
                else:
                    output[ATTR_TITLE_TEXT] = item.get(CONF_TITLE)

            if item.get(CONF_TEXT) is not None:
                if isinstance(item.get(CONF_TEXT), template.Template):
                    output[ATTR_MAIN_TEXT] = item[CONF_TEXT].async_render()
                else:
                    output[ATTR_MAIN_TEXT] = item.get(CONF_TEXT)

            if item.get(CONF_UID) is not None:
                output[ATTR_UID] = item.get(CONF_UID)

            if item.get(CONF_AUDIO) is not None:
                if isinstance(item.get(CONF_AUDIO), template.Template):
                    output[ATTR_STREAM_URL] = item[CONF_AUDIO].async_render()
                else:
                    output[ATTR_STREAM_URL] = item.get(CONF_AUDIO)

            if item.get(CONF_DISPLAY_URL) is not None:
                if isinstance(item.get(CONF_DISPLAY_URL),
                              template.Template):
                    output[ATTR_REDIRECTION_URL] = \
                        item[CONF_DISPLAY_URL].async_render()
                else:
                    output[ATTR_REDIRECTION_URL] = item.get(CONF_DISPLAY_URL)

            output[ATTR_UPDATE_DATE] = datetime.now().strftime(DATE_FORMAT)

            briefing.append(output)

        return self.json(briefing)
