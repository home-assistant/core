"""Text-to-speech constants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SpeechManager, TextToSpeechEntity

ATTR_CACHE = "cache"
ATTR_LANGUAGE = "language"
ATTR_MESSAGE = "message"
ATTR_OPTIONS = "options"

CONF_CACHE = "cache"
CONF_CACHE_DIR = "cache_dir"
CONF_FIELDS = "fields"
CONF_TIME_MEMORY = "time_memory"

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300

DOMAIN = "tts"
DATA_COMPONENT: HassKey[EntityComponent[TextToSpeechEntity]] = HassKey(DOMAIN)

DATA_TTS_MANAGER: HassKey[SpeechManager] = HassKey("tts_manager")

type TtsAudioType = tuple[str | None, bytes | None]
