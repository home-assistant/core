"""
Support for the google speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_speech/
"""
import asyncio
import os

import yarl
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.config import load_yaml_config_file
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_SPEECH, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
import homeassistant.helpers.config_validation as cv

DOMAIN = 'google_speech'
REQUIREMENTS = ["gTTS-token==1.1.1"]

SERVICE_SAY = 'say'

CONF_LANG = 'lang'
ATTR_MESSAGE = 'message'

DEFAULT_CONF_LANG = 'en'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_LANG, default=DEFAULT_CONF_LANG):
            vol.All(cv.string, vol.util.Lower)
    }),
}, extra=vol.ALLOW_EXTRA)


SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def say(hass, message, entity_id=None):
    """Call service say."""
    data = {ATTR_MESSAGE: message}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SAY, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup Google speech component."""
    from gtts_token import gtts_token

    token = gtts_token.Token()
    lang = config[DOMAIN].get(CONF_LANG)
    url_template = ("http://translate.google.com/translate_tts?"
                    "tl={}&q={}&tk={}&client=hass&textlen={}")

    @asyncio.coroutine
    def async_handle_say(service):
        """Service handle for say."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        message = yarl.quote(service.data.get(ATTR_MESSAGE))

        message_tok = yield from hass.loop.run_in_executor(
            None, token.calculate_token, message)
        url = url_template.format(lang, message, message_tok, len(message))

        data = {
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_SPEECH,
        }

        if entity_ids:
            data[ATTR_ENTITY_ID] = entity_ids

        yield from hass.services.async_call(
            DOMAIN_MP, SERVICE_PLAY_MEDIA, data, blocking=True)

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_SAY, async_handle_say, descriptions.get(SERVICE_SAY),
        schema=SCHEMA_SERVICE_SAY)

    return True
