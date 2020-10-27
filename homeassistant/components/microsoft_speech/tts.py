"""Support for the Microsoft Speech text-to-speech service based on Azure Cognitive Services."""
from http.client import HTTPException
import logging

from azure.cognitiveservices.speech import (
    AudioDataStream,
    CancellationReason,
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesizer,
)
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_API_KEY  # , CONF_TYPE, PERCENTAGE
import homeassistant.helpers.config_validation as cv

# CONF_GENDER = "gender"
CONF_OUTPUT = "output"
# CONF_RATE = "rate"
# CONF_VOLUME = "volume"
# CONF_PITCH = "pitch"
# CONF_CONTOUR = "contour"
CONF_REGION = "region"

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    # "ar-EG",
    # "ar-SA",
    # "bg-BG",
    # "ca-ES",
    # "cs-CZ",
    # "da-DK",
    # "de-AT",
    # "de-CH",
    # "de-DE",
    # "el-GR",
    # "en-AU",
    # "en-CA",
    # "en-GB",
    # "en-IE",
    # "en-IN",
    "en-US",
    # "es-ES",
    # "es-MX",
    # "fi-FI",
    # "fr-CA",
    # "fr-CH",
    # "fr-FR",
    # "he-IL",
    # "hi-IN",
    # "hr-HR",
    # "hu-HU",
    # "id-ID",
    # "it-IT",
    # "ja-JP",
    # "ko-KR",
    # "ms-MY",
    # "nb-NO",
    # "nl-NL",
    # "pl-PL",
    # "pt-BR",
    # "pt-PT",
    # "ro-RO",
    # "ru-RU",
    # "sk-SK",
    # "sl-SI",
    # "sv-SE",
    # "ta-IN",
    # "te-IN",
    # "th-TH",
    # "tr-TR",
    # "vi-VN",
    # "zh-CN",
    # "zh-HK",
    # "zh-TW",
]

# GENDERS = ["Female", "Male"]

DEFAULT_LANG = "en-us"
# DEFAULT_GENDER = "Female"
# DEFAULT_TYPE = "ZiraRUS"
DEFAULT_OUTPUT = "Audio16Khz128KBitRateMonoMp3"
# DEFAULT_RATE = 0
# DEFAULT_VOLUME = 0
# DEFAULT_PITCH = "default"
# DEFAULT_CONTOUR = ""
DEFAULT_REGION = "eastus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        # vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): vol.In(GENDERS),
        # vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
        # vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
        #     vol.Coerce(int), vol.Range(-100, 100)
        # ),
        # vol.Optional(CONF_VOLUME, default=DEFAULT_VOLUME): vol.All(
        #     vol.Coerce(int), vol.Range(-100, 100)
        # ),
        # vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): cv.string,
        # vol.Optional(CONF_CONTOUR, default=DEFAULT_CONTOUR): cv.string,
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up Microsoft speech component."""
    return MicrosoftProvider(
        config[CONF_API_KEY],
        config[CONF_REGION],
        config[CONF_LANG],
        # config[CONF_GENDER],
        # config[CONF_TYPE],
        # config[CONF_RATE],
        # config[CONF_VOLUME],
        # config[CONF_PITCH],
        # config[CONF_CONTOUR],
    )


class MicrosoftProvider(Provider):
    """The Microsoft Speech API provider."""

    def __init__(
        self, apikey, region, lang  # , gender, ttype, rate, volume, pitch, contour,
    ):
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._region = region
        self._lang = lang
        # self._gender = gender
        # self._type = ttype
        self._output = DEFAULT_OUTPUT
        # self._rate = f"{rate}{PERCENTAGE}"
        # self._volume = f"{volume}{PERCENTAGE}"
        # self._pitch = pitch
        # self._contour = contour
        self.name = "Microsoft"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from Microsoft."""
        if language is None:
            language = self._lang

        try:
            speech_config = SpeechConfig(subscription=self._apikey, region=self._region)
            speech_config.set_speech_synthesis_output_format(
                SpeechSynthesisOutputFormat[self._output]
            )
            synthesizer = SpeechSynthesizer(
                speech_config=speech_config, audio_config=None
            )

            result = synthesizer.speak_text_async(message).get()
            data = result.audio_data

            if result.reason == ResultReason.SynthesizingAudioCompleted:
                _LOGGER.debug(f"Speech synthesized for text [{message}]")
                stream = AudioDataStream(result)

                # Reads data from the stream
                audio_buffer = bytes(16000)
                total_size = 0
                filled_size = stream.read_data(audio_buffer)
                while filled_size > 0:
                    _LOGGER.debug(f"{filled_size} bytes received.")
                    total_size += filled_size
                    filled_size = stream.read_data(audio_buffer)
                _LOGGER.debug(
                    "Totally {} bytes received for text [{}].".format(
                        total_size, message
                    )
                )

            elif result.reason == ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                _LOGGER.info(
                    f"Speech synthesis canceled: {cancellation_details.reason}"
                )
                if cancellation_details.reason == CancellationReason.Error:
                    _LOGGER.error(
                        f"Error details: {cancellation_details.error_details}"
                    )
        except HTTPException as ex:
            _LOGGER.error("Error occurred for Microsoft TTS: %s", ex)
            return (None, None)
        return ("wav", data)
