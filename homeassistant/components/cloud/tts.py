"""Support for the cloud for text-to-speech service."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from hass_nabucasa import Cloud
from hass_nabucasa.voice import MAP_VOICE, TTS_VOICES, AudioOutput, VoiceError
import voluptuous as vol

from homeassistant.components.tts import (
    ATTR_AUDIO_OUTPUT,
    ATTR_VOICE,
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .assist_pipeline import async_migrate_cloud_pipeline_engine
from .client import CloudClient
from .const import DATA_PLATFORMS_SETUP, DOMAIN, TTS_ENTITY_UNIQUE_ID
from .prefs import CloudPreferences

ATTR_GENDER = "gender"

DEPRECATED_VOICES = {"XiaoxuanNeural": "XiaozhenNeural"}
SUPPORT_LANGUAGES = list(TTS_VOICES)

_LOGGER = logging.getLogger(__name__)


def validate_lang(value: dict[str, Any]) -> dict[str, Any]:
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
    TTS_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_LANG): str,
            vol.Optional(ATTR_GENDER): str,
        }
    ),
    validate_lang,
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CloudProvider:
    """Set up Cloud speech component."""
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]

    language: str | None
    gender: str | None
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud text-to-speech platform."""
    tts_platform_loaded: asyncio.Event = hass.data[DATA_PLATFORMS_SETUP][Platform.TTS]
    tts_platform_loaded.set()
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]
    async_add_entities([CloudTTSEntity(cloud)])


class CloudTTSEntity(TextToSpeechEntity):
    """Home Assistant Cloud text-to-speech entity."""

    _attr_name = "Home Assistant Cloud"
    _attr_unique_id = TTS_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize cloud text-to-speech entity."""
        self.cloud = cloud
        self._language, self._gender = cloud.client.prefs.tts_default_voice

    async def _sync_prefs(self, prefs: CloudPreferences) -> None:
        """Sync preferences."""
        self._language, self._gender = prefs.tts_default_voice

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._language

    @property
    def default_options(self) -> dict[str, Any]:
        """Return a dict include default options."""
        return {
            ATTR_GENDER: self._gender,
            ATTR_AUDIO_OUTPUT: AudioOutput.MP3,
        }

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotion."""
        return [ATTR_GENDER, ATTR_VOICE, ATTR_AUDIO_OUTPUT]

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        await async_migrate_cloud_pipeline_engine(
            self.hass, platform=Platform.TTS, engine_id=self.entity_id
        )
        self.async_on_remove(
            self.cloud.client.prefs.async_listen_updates(self._sync_prefs)
        )

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := TTS_VOICES.get(language)):
            return None
        return [Voice(voice, voice) for voice in voices]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Home Assistant Cloud."""
        original_voice: str | None = options.get(ATTR_VOICE)
        voice = handle_deprecated_voice(self.hass, original_voice)
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                text=message,
                language=language,
                gender=options.get(ATTR_GENDER),
                voice=voice,
                output=options[ATTR_AUDIO_OUTPUT],
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return (None, None)

        return (str(options[ATTR_AUDIO_OUTPUT].value), data)


class CloudProvider(Provider):
    """Home Assistant Cloud speech API provider."""

    def __init__(
        self, cloud: Cloud[CloudClient], language: str | None, gender: str | None
    ) -> None:
        """Initialize cloud provider."""
        self.cloud = cloud
        self.name = "Cloud"
        self._language = language
        self._gender = gender

        if self._language is not None:
            return

        self._language, self._gender = cloud.client.prefs.tts_default_voice
        cloud.client.prefs.async_listen_updates(self._sync_prefs)

    async def _sync_prefs(self, prefs: CloudPreferences) -> None:
        """Sync preferences."""
        self._language, self._gender = prefs.tts_default_voice

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotion."""
        return [ATTR_GENDER, ATTR_VOICE, ATTR_AUDIO_OUTPUT]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := TTS_VOICES.get(language)):
            return None
        return [Voice(voice, voice) for voice in voices]

    @property
    def default_options(self) -> dict[str, Any]:
        """Return a dict include default options."""
        return {
            ATTR_GENDER: self._gender,
            ATTR_AUDIO_OUTPUT: AudioOutput.MP3,
        }

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from Home Assistant Cloud."""
        original_voice: str | None = options.get(ATTR_VOICE)
        assert self.hass is not None
        voice = handle_deprecated_voice(self.hass, original_voice)
        # Process TTS
        try:
            data = await self.cloud.voice.process_tts(
                text=message,
                language=language,
                gender=options.get(ATTR_GENDER),
                voice=voice,
                output=options[ATTR_AUDIO_OUTPUT],
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return (None, None)

        return (str(options[ATTR_AUDIO_OUTPUT].value), data)


@callback
def handle_deprecated_voice(
    hass: HomeAssistant,
    original_voice: str | None,
) -> str | None:
    """Handle deprecated voice."""
    voice = original_voice
    if (
        original_voice
        and voice
        and (voice := DEPRECATED_VOICES.get(original_voice, original_voice))
        != original_voice
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_voice_{original_voice}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            breaks_in_ha_version="2024.8.0",
            translation_key="deprecated_voice",
            translation_placeholders={
                "deprecated_voice": original_voice,
                "replacement_voice": voice,
            },
        )
    return voice
