"""Support for playback of Google Assistant's audio response."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA,
    Provider,
    TtsAudioType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import SUPPORTED_LANGUAGE_CODES
from .helpers import async_send_text_command_with_audio, default_language_code

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG): vol.In(SUPPORTED_LANGUAGE_CODES),
    }
)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType | None,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up Google Assistant SDK TTS provider."""
    return GoogleAssistantSDKProvider(hass)


class GoogleAssistantSDKProvider(Provider):
    """The Google Assistant SDK TTS provider."""

    hass: HomeAssistant

    def __init__(self, hass):
        """Init Google Assistant SDK TTS provider."""
        self.hass = hass
        self.name = "Google Assistant SDK"

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return default_language_code(self.hass)

    @property
    def supported_languages(self) -> list[str] | None:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGE_CODES

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load tts audio file from provider.

        Return a tuple of file extension and data as bytes.
        """
        return "mp3", await async_send_text_command_with_audio(self.hass, message)
