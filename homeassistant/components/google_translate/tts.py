"""Support for the Google speech service."""

from __future__ import annotations

from io import BytesIO
import logging
from typing import Any

from gtts import gTTS, gTTSError
import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_TLD,
    DEFAULT_LANG,
    DEFAULT_TLD,
    MAP_LANG_TLD,
    SUPPORT_LANGUAGES,
    SUPPORT_TLD,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_OPTIONS = ["tld"]

PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_TLD, default=DEFAULT_TLD): vol.In(SUPPORT_TLD),
    }
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> GoogleProvider:
    """Set up Google speech component."""
    return GoogleProvider(hass, config[CONF_LANG], config[CONF_TLD])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Translate speech platform via config entry."""
    default_language = config_entry.data[CONF_LANG]
    default_tld = config_entry.data[CONF_TLD]
    async_add_entities([GoogleTTSEntity(config_entry, default_language, default_tld)])


class GoogleTTSEntity(TextToSpeechEntity):
    """The Google speech API entity."""

    def __init__(self, config_entry: ConfigEntry, lang: str, tld: str) -> None:
        """Init Google TTS service."""
        if lang in MAP_LANG_TLD:
            self._lang = MAP_LANG_TLD[lang].lang
            self._tld = MAP_LANG_TLD[lang].tld
        else:
            self._lang = lang
            self._tld = tld
        self._attr_name = f"Google Translate {self._lang} {self._tld}"
        self._attr_unique_id = config_entry.entry_id

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load TTS from google."""
        tld = self._tld
        if language in MAP_LANG_TLD:
            tld_language = MAP_LANG_TLD[language]
            tld = tld_language.tld
            language = tld_language.lang
        if options is not None and "tld" in options:
            tld = options["tld"]

        tts = gTTS(text=message, lang=language, tld=tld)
        mp3_data = BytesIO()

        try:
            tts.write_to_fp(mp3_data)
        except gTTSError as exc:
            _LOGGER.debug(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc

        return "mp3", mp3_data.getvalue()


class GoogleProvider(Provider):
    """The Google speech API provider."""

    def __init__(self, hass: HomeAssistant, lang: str, tld: str) -> None:
        """Init Google TTS service."""
        self.hass = hass
        if lang in MAP_LANG_TLD:
            self._lang = MAP_LANG_TLD[lang].lang
            self._tld = MAP_LANG_TLD[lang].tld
        else:
            self._lang = lang
            self._tld = tld
        self.name = "Google Translate"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from google."""
        tld = self._tld
        if language in MAP_LANG_TLD:
            tld = MAP_LANG_TLD[language].tld
            language = MAP_LANG_TLD[language].lang
        if "tld" in options:
            tld = options["tld"]
        tts = gTTS(text=message, lang=language, tld=tld)
        mp3_data = BytesIO()

        try:
            tts.write_to_fp(mp3_data)
        except gTTSError:
            _LOGGER.exception("Error during processing of TTS request")
            return None, None

        return "mp3", mp3_data.getvalue()
