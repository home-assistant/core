"""Support for the demo for text-to-speech service."""

from __future__ import annotations

import os
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

SUPPORT_LANGUAGES = ["en", "de"]

DEFAULT_LANG = "en"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
)


def get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Provider:
    """Set up Demo speech component."""
    return DemoProvider(config.get(CONF_LANG, DEFAULT_LANG))


class DemoProvider(Provider):
    """Demo speech API provider."""

    def __init__(self, lang: str) -> None:
        """Initialize demo provider."""
        self._lang = lang
        self.name = "Demo"

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
        """Return list of supported options like voice, emotions."""
        return ["voice", "age"]

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS from demo."""
        filename = os.path.join(os.path.dirname(__file__), "tts.mp3")
        try:
            with open(filename, "rb") as voice:
                data = voice.read()
        except OSError:
            return (None, None)

        return ("mp3", data)
