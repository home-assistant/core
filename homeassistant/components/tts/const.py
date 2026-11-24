"""Text-to-speech constants."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SpeechManager, TextToSpeechEntity

ATTR_CACHE = "cache"
ATTR_LANGUAGE = "language"
ATTR_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"
ATTR_MESSAGE = "message"
ATTR_OPTIONS = "options"

CONF_CACHE = "cache"
CONF_CACHE_DIR = "cache_dir"
CONF_FIELDS = "fields"
CONF_TIME_MEMORY = "time_memory"

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300

DOMAIN: Final = "tts"
DATA_COMPONENT: HassKey[EntityComponent[TextToSpeechEntity]] = HassKey(DOMAIN)

DATA_TTS_MANAGER: HassKey[SpeechManager] = HassKey("tts_manager")

MEDIA_SOURCE_STREAM_PATH = "-stream-"

SERVICE_CLEAR_CACHE = "clear_cache"

type TtsAudioType = tuple[str | None, bytes | None]


class TextToSpeechCommonOption(StrEnum):
    """Store keys for the text-to-speech options common to all engines."""

    AUDIO_OUTPUT = "audio_output"
    PREFERRED_BITRATE = "preferred_bitrate"
    PREFERRED_FORMAT = "preferred_format"
    PREFERRED_SAMPLE_BYTES = "preferred_sample_bytes"
    PREFERRED_SAMPLE_CHANNELS = "preferred_sample_channels"
    PREFERRED_SAMPLE_RATE = "preferred_sample_rate"
    VOICE = "voice"


class TextToSpeechService(StrEnum):
    """Store keys for text-to-speech services."""

    CLEAR_CACHE = "clear_cache"
    SPEAK = "speak"


class TextToSpeechServiceArgument(StrEnum):
    """Store keys for text-to-speech service arguments."""

    CACHE = "cache"
    DAYS = "days"
    LANGUAGE = "language"
    MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"
    MESSAGE = "message"
    OPTIONS = "options"
