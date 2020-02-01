"""Support for the cloud for text to speech service."""

from hass_nabucasa import Cloud
from hass_nabucasa.voice import VoiceError
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

from .const import DOMAIN

CONF_GENDER = "gender"

SUPPORT_LANGUAGES = ["en-US", "de-DE", "es-ES"]
SUPPORT_GENDER = ["male", "female"]

DEFAULT_LANG = "en-US"
DEFAULT_GENDER = "female"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): vol.In(SUPPORT_GENDER),
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Cloud speech component."""
    cloud: Cloud = hass.data[DOMAIN]

    if discovery_info is not None:
        language = DEFAULT_LANG
        gender = DEFAULT_GENDER
    else:
        language = config[CONF_LANG]
        gender = config[CONF_GENDER]

    return CloudProvider(cloud, language, gender)


class CloudProvider(Provider):
    """NabuCasa Cloud speech API provider."""

    def __init__(self, cloud: Cloud, language: str, gender: str):
        """Initialize cloud provider."""
        self.cloud = cloud
        self.name = "Cloud"
        self._language = language
        self._gender = gender

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
        return [CONF_GENDER]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {CONF_GENDER: self._gender}

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from NabuCasa Cloud."""
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                message, language, gender=options[CONF_GENDER]
            )
        except VoiceError:
            return (None, None)

        return ("mp3", data)
