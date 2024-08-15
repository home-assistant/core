"""Support for the Google Cloud TTS service."""

import logging
import os

from google.api_core.exceptions import GoogleAPIError
from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    Voice,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ENCODING,
    CONF_GAIN,
    CONF_GENDER,
    CONF_KEY_FILE,
    CONF_PITCH,
    CONF_PROFILES,
    CONF_SPEED,
    CONF_TEXT_TYPE,
    CONF_VOICE,
    DEFAULT_LANG,
)
from .helpers import async_tts_voices, tts_options_schema, tts_platform_schema

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(tts_platform_schema().schema)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google Cloud TTS component."""
    if key_file := config.get(CONF_KEY_FILE):
        key_file = hass.config.path(key_file)
        if not os.path.isfile(key_file):
            _LOGGER.error("File %s doesn't exist", key_file)
            return None
    if key_file:
        client = texttospeech.TextToSpeechAsyncClient.from_service_account_json(
            key_file
        )
    else:
        client = texttospeech.TextToSpeechAsyncClient()
    try:
        voices = await async_tts_voices(client)
    except GoogleAPIError as err:
        _LOGGER.error("Error from calling list_voices: %s", err)
        return None
    return GoogleCloudTTSProvider(
        hass,
        client,
        voices,
        config.get(CONF_LANG, DEFAULT_LANG),
        tts_options_schema(config, voices),
    )


class GoogleCloudTTSProvider(Provider):
    """The Google Cloud TTS API provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: texttospeech.TextToSpeechAsyncClient,
        voices: dict[str, list[str]],
        language,
        options_schema,
    ) -> None:
        """Init Google Cloud TTS service."""
        self.hass = hass
        self.name = "Google Cloud TTS"
        self._client = client
        self._voices = voices
        self._language = language
        self._options_schema = options_schema

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return list(self._voices)

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return [option.schema for option in self._options_schema.schema]

    @property
    def default_options(self):
        """Return a dict including default options."""
        return self._options_schema({})

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := self._voices.get(language)):
            return None
        return [Voice(voice, voice) for voice in voices]

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from google."""
        try:
            options = self._options_schema(options)
        except vol.Invalid as err:
            _LOGGER.error("Error: %s when validating options: %s", err, options)
            return None, None

        encoding = texttospeech.AudioEncoding[options[CONF_ENCODING]]
        gender = texttospeech.SsmlVoiceGender[options[CONF_GENDER]]
        voice = options[CONF_VOICE]
        if voice:
            gender = None
            if not voice.startswith(language):
                language = voice[:5]

        request = texttospeech.SynthesizeSpeechRequest(
            input=texttospeech.SynthesisInput(**{options[CONF_TEXT_TYPE]: message}),
            voice=texttospeech.VoiceSelectionParams(
                language_code=language,
                ssml_gender=gender,
                name=voice,
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=encoding,
                speaking_rate=options[CONF_SPEED],
                pitch=options[CONF_PITCH],
                volume_gain_db=options[CONF_GAIN],
                effects_profile_id=options[CONF_PROFILES],
            ),
        )

        try:
            response = await self._client.synthesize_speech(request, timeout=10)
        except GoogleAPIError as err:
            _LOGGER.error("Error occurred during Google Cloud TTS call: %s", err)
            return None, None

        if encoding == texttospeech.AudioEncoding.MP3:
            extension = "mp3"
        elif encoding == texttospeech.AudioEncoding.OGG_OPUS:
            extension = "ogg"
        else:
            extension = "wav"

        return extension, response.audio_content
