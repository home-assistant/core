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
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

CONF_OUTPUT = "output"
CONF_REGION = "region"

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    "en-US",
]

DEFAULT_LANG = "en-us"
DEFAULT_OUTPUT = "Audio16Khz128KBitRateMonoMp3"
DEFAULT_REGION = "eastus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up Microsoft Speech component."""
    return MicrosoftProvider(
        config[CONF_API_KEY],
        config[CONF_REGION],
        config[CONF_LANG],
    )


class MicrosoftProvider(Provider):
    """The Microsoft Speech API provider."""

    def __init__(self, apikey, region, lang):
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._region = region
        self._lang = lang
        self._output = DEFAULT_OUTPUT
        self.name = "Microsoft Speech"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from Microsoft Speech."""
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
