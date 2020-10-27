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
from homeassistant.const import CONF_API_KEY, CONF_TYPE
import homeassistant.helpers.config_validation as cv

from .const import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_OUTPUTS,
    SUPPORTED_REGIONS,
    SUPPORTED_TYPES,
    SUPPORTED_VOICES,
)

CONF_OUTPUT = "output"
CONF_REGION = "region"

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANG = "en-US"
DEFAULT_TYPE = "AriaNeural"
DEFAULT_OUTPUT = "Audio16Khz128KBitRateMonoMp3"
DEFAULT_REGION = "eastus"
DEFAULT_VOICE = f"{DEFAULT_LANG}-{DEFAULT_TYPE}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.In(SUPPORTED_TYPES),
        vol.Optional(CONF_OUTPUT, default=DEFAULT_OUTPUT): vol.In(SUPPORTED_OUTPUTS),
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up Microsoft Speech component."""
    return MicrosoftProvider(
        config[CONF_API_KEY],
        config[CONF_REGION],
        config[CONF_OUTPUT],
        config[CONF_LANG],
        config[CONF_TYPE],
    )


class MicrosoftProvider(Provider):
    """The Microsoft Speech API provider."""

    def __init__(self, apikey, region, output, lang, ttype):
        """Init Microsoft TTS service."""
        self._apikey = apikey
        self._region = region
        self._lang = lang
        self._type = ttype
        self._voice = f"{lang}-{ttype}"
        self._output = output
        self.name = "Microsoft Speech"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_types(self):
        """Return list of supported types."""
        return SUPPORTED_TYPES

    @property
    def supported_voices(self):
        """Return list of supported voices."""
        return SUPPORTED_VOICES

    @property
    def supported_outputs(self):
        """Return list of supported outputs."""
        return SUPPORTED_OUTPUTS

    @property
    def supported_regions(self):
        """Return list of supported regions."""
        return SUPPORTED_REGIONS

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from Microsoft Speech."""
        if language is None:
            language = self._lang

        if self._voice in self.supported_voices:
            pass
        else:
            _LOGGER.error(
                "The provided voice %s is not in the supported types list. Falling back to default voice %s",
                self._voice,
                DEFAULT_VOICE,
            )
            self._voice = DEFAULT_VOICE

        try:
            speech_config = SpeechConfig(subscription=self._apikey, region=self._region)

            speech_config.set_speech_synthesis_output_format(
                SpeechSynthesisOutputFormat[self._output]
            )
            speech_config.speech_synthesis_voice_name = self._voice
            synthesizer = SpeechSynthesizer(
                speech_config=speech_config, audio_config=None
            )

            result = synthesizer.speak_text_async(message).get()
            data = result.audio_data

            if result.reason == ResultReason.SynthesizingAudioCompleted:
                _LOGGER.debug("Speech synthesized for text [%s]", message)
                stream = AudioDataStream(result)

                # Reads data from the stream
                audio_buffer = bytes(16000)
                total_size = 0
                filled_size = stream.read_data(audio_buffer)
                while filled_size > 0:
                    _LOGGER.debug("%s bytes received.", filled_size)
                    total_size += filled_size
                    filled_size = stream.read_data(audio_buffer)
                _LOGGER.debug(
                    "Totally %s bytes received for text [%s].", total_size, message
                )

            elif result.reason == ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                _LOGGER.info(
                    "Speech synthesis canceled: %s", cancellation_details.reason
                )
                if cancellation_details.reason == CancellationReason.Error:
                    _LOGGER.error("Error details: %s", cancellation_details.reason)
        except HTTPException as ex:
            _LOGGER.error("Error occurred for Microsoft TTS: %s", ex)
            return (None, None)
        return ("wav", data)
