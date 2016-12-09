"""
Support for the google speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tts/google/
"""
import asyncio
import logging

import aiohttp
import async_timeout
import yarl

from homeassistant.components.tts import Provider
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ["gTTS-token==1.1.1"]

_LOGGER = logging.getLogger(__name__)
GOOGLE_SPEECH_URL = ("http://translate.google.com/translate_tts?"
                     "tl={}&q={}&tk={}&client=hass&textlen={}")


@asyncio.coroutine
def async_get_engine(hass, config):
    """Setup Google speech component."""
    return GoogleProvider(hass)


class GoogleProvider(Provider):
    """Google speech api provider."""

    def __init__(self, hass):
        """Init Google TTS service."""
        from gtts_token import gtts_token

        self.hass = hass
        self.token = gtts_token.Token()

    @property
    def file_format(self):
        """Return file/audio format."""
        return "mp3"

    @property
    def content_type(self):
        """Return file/audio format."""
        return "audio/mpeg"

    @asyncio.coroutine
    def async_run_tts(self, message):
        """Load TTS from google."""
        message = yarl.quote(message)
        message_tok = yield from self.hass.loop.run_in_executor(
            None, self.token.calculate_token, message)
        url = GOOGLE_SPEECH_URL.format(
            self.language, message, message_tok, len(message))
        websession = async_get_clientsession(self.hass)

        try:
            request = None
            with async_timeout.timeout(10, loop=self.hass.loop):
                request = yield from websession.get(url)
                data = yield from request.read()

        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error("Timeout from %s", url)
            return

        finally:
            if request is not None:
                yield from request.release()

        return data
