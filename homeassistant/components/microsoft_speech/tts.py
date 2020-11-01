"""Support for the Microsoft Speech text-to-speech service based on Azure Cognitive Services."""
import logging

from azure.cognitiveservices.speech import (
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesizer,
)
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider
from homeassistant.const import CONF_API_KEY, CONF_REGION, CONF_TYPE
import homeassistant.helpers.config_validation as cv

from .const import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_OUTPUTS,
    SUPPORTED_REGIONS,
    SUPPORTED_TYPES,
    SUPPORTED_VOICES,
)

CONF_OUTPUT = "output"

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANG = "en-US"
DEFAULT_TYPE = "AriaNeural"
DEFAULT_OUTPUT = "Audio16Khz128KBitRateMonoMp3"
DEFAULT_REGION = "eastus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.In(SUPPORTED_TYPES),
        vol.Optional(CONF_OUTPUT, default=DEFAULT_OUTPUT): vol.In(SUPPORTED_OUTPUTS),
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
        self.name = "Microsoft_Speech"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_voices(self):
        """Return list of supported voices."""
        return SUPPORTED_VOICES

    def validate_voice(self):
        """Validate voice against the list of supported voices."""
        if self._voice not in self.supported_voices:
            _LOGGER.warning(
                "Selected voice '%s' not in supported voices list. Please validate the combination of 'language' and 'type' in your configuration",
                self._voice,
            )
        else:
            pass

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from Microsoft Speech."""
        self.validate_voice()

        speech_config = SpeechConfig(subscription=self._apikey, region=self._region)

        speech_config.set_speech_synthesis_output_format(
            SpeechSynthesisOutputFormat[self._output]
        )
        speech_config.speech_synthesis_voice_name = self._voice

        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)

        result = synthesizer.speak_text_async(message).get()
        data = result.audio_data

        return ("wav", data)
