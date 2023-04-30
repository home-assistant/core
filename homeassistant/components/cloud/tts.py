"""Support for the cloud for text to speech service."""

import logging

from hass_nabucasa import Cloud
from hass_nabucasa.voice import MAP_VOICE, TTS_VOICES, AudioOutput, VoiceError
import voluptuous as vol

from homeassistant.components.tts import (
    ATTR_AUDIO_OUTPUT,
    ATTR_VOICE,
    CONF_LANG,
    PLATFORM_SCHEMA,
    Provider,
    Voice,
)
from homeassistant.core import callback

from .const import DOMAIN

ATTR_GENDER = "gender"

SUPPORT_LANGUAGES = list(TTS_VOICES)

_LOGGER = logging.getLogger(__name__)


def validate_lang(value):
    """Validate chosen gender or language."""
    if (lang := value.get(CONF_LANG)) is None:
        return value

    if (gender := value.get(ATTR_GENDER)) is None:
        gender = value[ATTR_GENDER] = next(
            (chk_gender for chk_lang, chk_gender in MAP_VOICE if chk_lang == lang), None
        )

    if (lang, gender) not in MAP_VOICE:
        raise vol.Invalid("Unsupported language and gender specified.")

    return value


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_LANG): str,
            vol.Optional(ATTR_GENDER): str,
        }
    ),
    validate_lang,
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Cloud speech component."""
    cloud: Cloud = hass.data[DOMAIN]

    if discovery_info is not None:
        language = None
        gender = None
    else:
        language = config[CONF_LANG]
        gender = config[ATTR_GENDER]

    cloud_provider = CloudProvider(cloud, language, gender)
    if discovery_info is not None:
        discovery_info["platform_loaded"].set()
    return cloud_provider


class CloudProvider(Provider):
    """NabuCasa Cloud speech API provider."""

    def __init__(self, cloud: Cloud, language: str, gender: str) -> None:
        """Initialize cloud provider."""
        self.cloud = cloud
        self.name = "Cloud"
        self._language = language
        self._gender = gender

        if self._language is not None:
            return

        self._language, self._gender = cloud.client.prefs.tts_default_voice
        cloud.client.prefs.async_listen_updates(self._sync_prefs)

    async def _sync_prefs(self, prefs):
        """Sync preferences."""
        self._language, self._gender = prefs.tts_default_voice

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self):
        """Return list of supported options like voice, emotion."""
        return [ATTR_GENDER, ATTR_VOICE, ATTR_AUDIO_OUTPUT]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := TTS_VOICES.get(language)):
            return None
        return [Voice(voice, voice) for voice in voices]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {
            ATTR_GENDER: self._gender,
            ATTR_AUDIO_OUTPUT: AudioOutput.MP3,
        }

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from NabuCasa Cloud."""
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                text=message,
                language=language,
                gender=options.get(ATTR_GENDER),
                voice=options.get(ATTR_VOICE),
                output=options[ATTR_AUDIO_OUTPUT],
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return (None, None)

        return (str(options[ATTR_AUDIO_OUTPUT]), data)
