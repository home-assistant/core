"""Integration support for the F5 TTS platform."""

import asyncio
import logging
from typing import Any, Literal

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    STATE_OK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .audio_processor import AudioProcessor
from .connection import ConnectionClient
from .const import DOMAIN
from .utils import split_text_min_chunks

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = ["en"]
DEFAULT_LANG = "en"

# Audio options
AUDIO_ENCODING = "utf-8"
AUDIO_INPUT_FORMAT = "f32le"
AUDIO_CHANNEL_MODE: Literal["1", "2"] = "1"  # stereo
AUDIO_STREAM_CHUNK_SIZE = 4096
AUDIO_INPUT_RATE = 24000
AUDIO_STREAM_TERMINATOR = b"END_OF_AUDIO"

# Misc
METADATA_DELIMITER = b"data"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TTS platform for F5 TTS Client."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([F5TTS(DEFAULT_LANG, config)])


class F5TTS(TextToSpeechEntity):
    """Main TTS entity."""

    _attr_has_entity_name = True

    def __init__(self, lang: str, config: dict[str, Any]) -> None:
        """Initialize prerequisites."""
        self._lang = lang
        self._status = STATE_UNKNOWN
        self.host = config[CONF_HOST]

        self.port = config[CONF_PORT]
        self.s_client = ConnectionClient(self.host, self.port)
        self.processor = AudioProcessor(
            AUDIO_CHANNEL_MODE, AUDIO_INPUT_FORMAT, AUDIO_INPUT_RATE
        )

    @property
    def name(self) -> str:
        """Return the name of the TTS entity."""
        return "F5 TTS Client"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the entity."""
        return f"f5_tts_{self.entity_id}"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def should_poll(self) -> bool:
        """Return True to enable polling."""
        return True

    async def async_update(self):
        """Periodically update the status of the TTS service."""
        try:
            await self.s_client.connect()
            self._status = STATE_OK
            await self.s_client.disconnect()
        except (TimeoutError, OSError):
            self._status = STATE_UNAVAILABLE

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ):
        """Load tts audio file from the engine."""
        word_chunks = split_text_min_chunks(message)
        async with asyncio.TaskGroup() as task_group:
            tasks = [
                task_group.create_task(self.process_audio(word)) for word in word_chunks
            ]

        results = [task.result() for task in tasks]
        wav_data = results[0]

        if len(results) > 1:
            # Handling multiple chanks and removing metadata from each
            metadata = (results[0].split(METADATA_DELIMITER))[0] + METADATA_DELIMITER
            wav_data = metadata
            for result in results:
                result = result.split(METADATA_DELIMITER)[1]
                wav_data += result

        return ("wav", wav_data)

    async def process_audio(self, message: str):
        """Handle the e2e flow for processing."""
        s_client = ConnectionClient(self.host, self.port)
        try:
            await s_client.connect()
            await s_client.send_message(message.lower())
            raw_message = await s_client.receive_message(
                AUDIO_STREAM_CHUNK_SIZE, AUDIO_STREAM_TERMINATOR
            )

            return self.processor.process_stream(raw_message)
        except Exception as e:
            _LOGGER.error(e)
            raise
        finally:
            if s_client.writer is not None:
                await s_client.disconnect()
