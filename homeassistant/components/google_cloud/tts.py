"""Support for the Google Cloud TTS service."""
import asyncio
import logging
import os

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
CONF_TEXT_TYPE = "text_type"

SUPPORTED_LANGUAGES = [
    "af-ZA",
    "ar-XA",
    "bg-BG",
    "bn-IN",
    "ca-ES",
    "cmn-CN",
    "cmn-TW",
    "cs-CZ",
    "da-DK",
    "de-DE",
    "el-GR",
    "en-AU",
    "en-GB",
    "en-IN",
    "en-US",
    "es-ES",
    "es-US",
    "eu-ES",
    "fi-FI",
    "fil-PH",
    "fr-CA",
    "fr-FR",
    "gl-ES",
    "gu-IN",
    "he-IL",
    "hi-IN",
    "hu-HU",
    "id-ID",
    "is-IS",
    "it-IT",
    "ja-JP",
    "kn-IN",
    "ko-KR",
    "lv-LV",
    "lt-LT",
    "ml-IN",
    "mr-IN",
    "ms-MY",
    "nb-NO",
    "nl-BE",
    "nl-NL",
    "pa-IN",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ro-RO",
    "ru-RU",
    "sk-SK",
    "sr-RS",
    "sv-SE",
    "ta-IN",
    "te-IN",
    "th-TH",
    "tr-TR",
    "uk-UA",
    "vi-VN",
    "yue-HK",
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

SUPPORTED_TEXT_TYPES = ["text", "ssml"]
DEFAULT_TEXT_TYPE = "text"

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
    CONF_TEXT_TYPE,
]

GENDER_SCHEMA = vol.All(vol.Upper, vol.In(texttospeech.SsmlVoiceGender.__members__))
VOICE_SCHEMA = cv.matches_regex(VOICE_REGEX)
SCHEMA_ENCODING = vol.All(vol.Upper, vol.In(texttospeech.AudioEncoding.__members__))
SPEED_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_SPEED, max=MAX_SPEED))
PITCH_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_PITCH, max=MAX_PITCH))
GAIN_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_GAIN, max=MAX_GAIN))
PROFILES_SCHEMA = vol.All(cv.ensure_list, [vol.In(SUPPORTED_PROFILES)])
TEXT_TYPE_SCHEMA = vol.All(vol.Lower, vol.In(SUPPORTED_TEXT_TYPES))

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
        vol.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): TEXT_TYPE_SCHEMA,
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google Cloud TTS component."""
    if key_file := config.get(CONF_KEY_FILE):
        key_file = hass.config.path(key_file)
        if not os.path.isfile(key_file):
            _LOGGER.error("File %s doesn't exist", key_file)
            return None

    return GoogleCloudTTSProvider(
        hass,
        key_file,
        config[CONF_LANG],
        config[CONF_GENDER],
        config[CONF_VOICE],
        config[CONF_ENCODING],
        config[CONF_SPEED],
        config[CONF_PITCH],
        config[CONF_GAIN],
        config[CONF_PROFILES],
        config[CONF_TEXT_TYPE],
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
        text_type=DEFAULT_TEXT_TYPE,
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
        self._text_type = text_type

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
            CONF_TEXT_TYPE: self._text_type,
        }

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from google."""
        options_schema = vol.Schema(
            {
                vol.Optional(CONF_GENDER, default=self._gender): GENDER_SCHEMA,
                vol.Optional(CONF_VOICE, default=self._voice): VOICE_SCHEMA,
                vol.Optional(CONF_ENCODING, default=self._encoding): SCHEMA_ENCODING,
                vol.Optional(CONF_SPEED, default=self._speed): SPEED_SCHEMA,
                vol.Optional(CONF_PITCH, default=self._pitch): PITCH_SCHEMA,
                vol.Optional(CONF_GAIN, default=self._gain): GAIN_SCHEMA,
                vol.Optional(CONF_PROFILES, default=self._profiles): PROFILES_SCHEMA,
                vol.Optional(CONF_TEXT_TYPE, default=self._text_type): TEXT_TYPE_SCHEMA,
            }
        )
        options = options_schema(options)

        _encoding = options[CONF_ENCODING]
        _voice = options[CONF_VOICE]
        if _voice and not _voice.startswith(language):
            language = _voice[:5]

        try:
            params = {options[CONF_TEXT_TYPE]: message}
            synthesis_input = texttospeech.SynthesisInput(**params)

            voice = texttospeech.VoiceSelectionParams(
                language_code=language,
                ssml_gender=texttospeech.SsmlVoiceGender[options[CONF_GENDER]],
                name=_voice,
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding[_encoding],
                speaking_rate=options[CONF_SPEED],
                pitch=options[CONF_PITCH],
                volume_gain_db=options[CONF_GAIN],
                effects_profile_id=options[CONF_PROFILES],
            )

            request = {
                "voice": voice,
                "audio_config": audio_config,
                "input": synthesis_input,
            }

            async with asyncio.timeout(10):
                assert self.hass
                response = await self.hass.async_add_executor_job(
                    self._client.synthesize_speech, request
                )
                return _encoding, response.audio_content

        except asyncio.TimeoutError as ex:
            _LOGGER.error("Timeout for Google Cloud TTS call: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error occurred during Google Cloud TTS call: %s", ex)

        return None, None
