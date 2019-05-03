"""Support for the Google Cloud TTS service."""
import logging
import os
import asyncio
import async_timeout
import voluptuous as vol
from google.cloud import texttospeech
from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    'en', 'da', 'nl', 'fr', 'de', 'it', 'ja', 'ko', 'nb',
    'pl', 'pt', 'ru', 'sk', 'es', 'sv', 'tr', 'uk',
]
DEFAULT_LANG = SUPPORTED_LANGUAGES[0]

SUPPORTED_GENDERS = [
    'Neutral', 'Female', 'Male',
]
DEFAULT_GENDER = SUPPORTED_GENDERS[0]
GENDERS_DICT = {
    'Neutral': texttospeech.enums.SsmlVoiceGender.NEUTRAL,
    'Female': texttospeech.enums.SsmlVoiceGender.FEMALE,
    'Male': texttospeech.enums.SsmlVoiceGender.MALE,
}

SUPPORTED_ENCODINGS = [
    'ogg', 'mp3', 'wav',
]
DEFAULT_ENCODING = SUPPORTED_ENCODINGS[0]
ENCODINGS_DICT = {
    'ogg': texttospeech.enums.AudioEncoding.OGG_OPUS,
    'mp3': texttospeech.enums.AudioEncoding.MP3,
    'wav': texttospeech.enums.AudioEncoding.LINEAR16,
}

CONF_GENDER = 'gender'
CONF_VOICE = 'voice'
CONF_ENCODING = 'encoding'
CONF_KEY_FILE = 'key_file'

SUPPORTED_OPTIONS = [
    CONF_VOICE, CONF_GENDER, CONF_ENCODING,
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
    vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): vol.In(SUPPORTED_GENDERS),
    vol.Optional(CONF_VOICE, default=''): cv.string,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
    vol.Optional(CONF_KEY_FILE, default=''): cv.string,
})


async def async_get_engine(hass, config):
    """Set up Google Cloud TTS component."""
    key_file = config[CONF_KEY_FILE]
    if key_file:
        key_file = hass.config.path(key_file)
        if not os.path.isfile(key_file):
            _LOGGER.error("API key file doesn't exist!")
            return None

    return GoogleCloudTTSProvider(
        hass,
        key_file,
        config[CONF_LANG],
        config[CONF_GENDER],
        config[CONF_VOICE],
        config[CONF_ENCODING]
    )


class GoogleCloudTTSProvider(Provider):
    """The Google Cloud TTS API provider."""

    def __init__(self, hass, key_file, lang, gender, voice, encoding):
        """Init Google Cloud TTS service."""
        self.hass = hass
        self.name = 'Google Cloud TTS'
        self._lang = lang
        self._gender = gender
        self._voice = voice
        self._encoding = encoding
        
        if key_file:
            self._client = texttospeech \
                .TextToSpeechClient.from_service_account_json(key_file)
        else:
            self._client = texttospeech.TextToSpeechClient()

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORTED_OPTIONS

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from google."""
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                _language = language or self._lang
                _gender = self._gender
                _voice = self._voice
                _encoding = self._encoding
                
                if options:
                    if CONF_GENDER in options:
                        _gender = options[CONF_GENDER].lower().capitalize()
                    if CONF_VOICE in options:
                        _voice = options[CONF_VOICE]
                    if CONF_ENCODING in options:
                        _encoding = options[CONF_ENCODING].lower()
                
                synthesis_input = texttospeech.types.SynthesisInput(
                    text=message
                )  # pylint: disable=no-member
                
                voice = texttospeech.types.VoiceSelectionParams(
                    language_code=_language,
                    ssml_gender=GENDERS_DICT.get(
                        _gender,
                        DEFAULT_GENDER
                    ),
                    name=_voice
                )  # pylint: disable=no-member
                
                audio_config = texttospeech.types.AudioConfig(
                    audio_encoding=ENCODINGS_DICT.get(
                        _encoding,
                        DEFAULT_ENCODING
                    )
                )  # pylint: disable=no-member
                response = await self.hass.async_add_executor_job(
                    self._client.synthesize_speech,
                    synthesis_input,
                    voice,
                    audio_config
                )
                return _encoding, response.audio_content

        except asyncio.TimeoutError as ex:
            _LOGGER.error("Timeout for Google Cloud TTS call: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Error occured during Google Cloud TTS call: %s", ex)

        return None, None
