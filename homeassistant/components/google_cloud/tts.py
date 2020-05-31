"""Support for the Google Cloud TTS service."""
import asyncio
import logging
import os

import async_timeout
from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_KEY_FILE = "key_file"
CONF_GENDER = "gender"
CONF_VOICE = "voice"
CONF_ENCODING = "encoding"
CONF_SPEED = "speed"
CONF_PITCH = "pitch"
CONF_GAIN = "gain"
CONF_PROFILES = "profiles"

SUPPORTED_LANGUAGES = [
    "ar-XA",
    "bn-IN",
    "cmn-CN",
    "cs-CZ",
    "da-DK",
    "de-DE",
    "el-GR",
    "en-AU",
    "en-GB",
    "en-IN",
    "en-US",
    "es-ES",
    "fi-FI",
    "fil-PH",
    "fr-CA",
    "fr-FR",
    "gu-IN",
    "hi-IN",
    "hu-HU",
    "id-ID",
    "it-IT",
    "ja-JP",
    "kn-IN",
    "ko-KR",
    "ml-IN",
    "nb-NO",
    "nl-NL",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ru-RU",
    "sk-SK",
    "sv-SE",
    "ta-IN",
    "te-IN",
    "th-TH",
    "tr-TR",
    "uk-UA",
    "vi-VN",
]
DEFAULT_LANG = "en-US"

DEFAULT_GENDER = "NEUTRAL"

VOICE_REGEX = r"[a-z]{2,3}-[A-Z]{2}-(Standard|Wavenet)-[A-Z]|"
DEFAULT_VOICE = ""

DEFAULT_ENCODING = "MP3"

MIN_SPEED = 0.25
MAX_SPEED = 4.0
DEFAULT_SPEED = 1.0

MIN_PITCH = -20.0
MAX_PITCH = 20.0
DEFAULT_PITCH = 0

MIN_GAIN = -96.0
MAX_GAIN = 16.0
DEFAULT_GAIN = 0

SUPPORTED_PROFILES = [
    "wearable-class-device",
    "handset-class-device",
    "headphone-class-device",
    "small-bluetooth-speaker-class-device",
    "medium-bluetooth-speaker-class-device",
    "large-home-entertainment-class-device",
    "large-automotive-class-device",
    "telephony-class-application",
]

SUPPORTED_OPTIONS = [
    CONF_VOICE,
    CONF_GENDER,
    CONF_ENCODING,
    CONF_SPEED,
    CONF_PITCH,
    CONF_GAIN,
    CONF_PROFILES,
]

GENDER_SCHEMA = vol.All(
    vol.Upper, vol.In(texttospeech.enums.SsmlVoiceGender.__members__)
)
VOICE_SCHEMA = cv.matches_regex(VOICE_REGEX)
SCHEMA_ENCODING = vol.All(
    vol.Upper, vol.In(texttospeech.enums.AudioEncoding.__members__)
)
SPEED_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_SPEED, max=MAX_SPEED))
PITCH_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_PITCH, max=MAX_PITCH))
GAIN_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_GAIN, max=MAX_GAIN))
PROFILES_SCHEMA = vol.All(cv.ensure_list, [vol.In(SUPPORTED_PROFILES)])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_KEY_FILE): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): GENDER_SCHEMA,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): VOICE_SCHEMA,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): SCHEMA_ENCODING,
        vol.Optional(CONF_SPEED, default=DEFAULT_SPEED): SPEED_SCHEMA,
        vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): PITCH_SCHEMA,
        vol.Optional(CONF_GAIN, default=DEFAULT_GAIN): GAIN_SCHEMA,
        vol.Optional(CONF_PROFILES, default=[]): PROFILES_SCHEMA,
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google Cloud TTS component."""
    key_file = config.get(CONF_KEY_FILE)
    if key_file:
        key_file = hass.config.path(key_file)
        if not os.path.isfile(key_file):
            _LOGGER.error("File %s doesn't exist", key_file)
            return None

    return GoogleCloudTTSProvider(
        hass,
        key_file,
        config.get(CONF_LANG),
        config.get(CONF_GENDER),
        config.get(CONF_VOICE),
        config.get(CONF_ENCODING),
        config.get(CONF_SPEED),
        config.get(CONF_PITCH),
        config.get(CONF_GAIN),
        config.get(CONF_PROFILES),
    )


class GoogleCloudTTSProvider(Provider):
    """The Google Cloud TTS API provider."""

    def __init__(
        self,
        hass,
        key_file=None,
        language=DEFAULT_LANG,
        gender=DEFAULT_GENDER,
        voice=DEFAULT_VOICE,
        encoding=DEFAULT_ENCODING,
        speed=1.0,
        pitch=0,
        gain=0,
        profiles=None,
    ):
        """Init Google Cloud TTS service."""
        self.hass = hass
        self.name = "Google Cloud TTS"
        self._language = language
        self._gender = gender
        self._voice = voice
        self._encoding = encoding
        self._speed = speed
        self._pitch = pitch
        self._gain = gain
        self._profiles = profiles

        if key_file:
            self._client = texttospeech.TextToSpeechClient.from_service_account_json(
                key_file
            )
        else:
            self._client = texttospeech.TextToSpeechClient()

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORTED_OPTIONS

    @property
    def default_options(self):
        """Return a dict including default options."""
        return {
            CONF_GENDER: self._gender,
            CONF_VOICE: self._voice,
            CONF_ENCODING: self._encoding,
            CONF_SPEED: self._speed,
            CONF_PITCH: self._pitch,
            CONF_GAIN: self._gain,
            CONF_PROFILES: self._profiles,
        }

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from google."""
        options_schema = vol.Schema(
            {
                vol.Optional(CONF_GENDER, default=self._gender): GENDER_SCHEMA,
                vol.Optional(CONF_VOICE, default=self._voice): VOICE_SCHEMA,
                vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): SCHEMA_ENCODING,
                vol.Optional(CONF_SPEED, default=self._speed): SPEED_SCHEMA,
                vol.Optional(CONF_PITCH, default=self._speed): SPEED_SCHEMA,
                vol.Optional(CONF_GAIN, default=DEFAULT_GAIN): GAIN_SCHEMA,
                vol.Optional(CONF_PROFILES, default=[]): PROFILES_SCHEMA,
            }
        )
        options = options_schema(options)

        _encoding = options[CONF_ENCODING]
        _voice = options[CONF_VOICE]
        if _voice and not _voice.startswith(language):
            language = _voice[:5]

        try:
            # pylint: disable=no-member
            synthesis_input = texttospeech.types.SynthesisInput(text=message)

            voice = texttospeech.types.VoiceSelectionParams(
                language_code=language,
                ssml_gender=texttospeech.enums.SsmlVoiceGender[options[CONF_GENDER]],
                name=_voice,
            )

            audio_config = texttospeech.types.AudioConfig(
                audio_encoding=texttospeech.enums.AudioEncoding[_encoding],
                speaking_rate=options.get(CONF_SPEED),
                pitch=options.get(CONF_PITCH),
                volume_gain_db=options.get(CONF_GAIN),
                effects_profile_id=options.get(CONF_PROFILES),
            )
            # pylint: enable=no-member

            with async_timeout.timeout(10, loop=self.hass.loop):
                response = await self.hass.async_add_executor_job(
                    self._client.synthesize_speech, synthesis_input, voice, audio_config
                )
                return _encoding, response.audio_content

        except asyncio.TimeoutError as ex:
            _LOGGER.error("Timeout for Google Cloud TTS call: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error occurred during Google Cloud TTS call: %s", ex)

        return None, None
