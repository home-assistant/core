"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, Mapping
import contextlib
import logging
from typing import Any

from elevenlabs import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice as ElevenLabsVoice, VoiceSettings
from sentence_stream import SentenceBoundaryDetector

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    TtsAudioType,
    Voice,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElevenLabsConfigEntry
from .const import (
    ATTR_MODEL,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
    MAX_REQUEST_IDS,
    MODELS_REQUEST_ID_NOT_SUPPORTED,
)

_LOGGER = logging.getLogger(__name__)


def to_voice_settings(options: Mapping[str, Any]) -> VoiceSettings:
    """Return voice settings."""
    return VoiceSettings(
        stability=options.get(CONF_STABILITY, DEFAULT_STABILITY),
        similarity_boost=options.get(CONF_SIMILARITY, DEFAULT_SIMILARITY),
        style=options.get(CONF_STYLE, DEFAULT_STYLE),
        use_speaker_boost=options.get(
            CONF_USE_SPEAKER_BOOST, DEFAULT_USE_SPEAKER_BOOST
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElevenLabsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    client = config_entry.runtime_data.client
    voices = (await client.voices.get_all()).voices
    default_voice_id = config_entry.options[CONF_VOICE]
    voice_settings = to_voice_settings(config_entry.options)
    async_add_entities(
        [
            ElevenLabsTTSEntity(
                client,
                config_entry.runtime_data.model,
                voices,
                default_voice_id,
                config_entry.entry_id,
                voice_settings,
            )
        ]
    )


class ElevenLabsTTSEntity(TextToSpeechEntity):
    """The ElevenLabs API entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_MODEL]
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "elevenlabs_tts"

    def __init__(
        self,
        client: AsyncElevenLabs,
        model: Model,
        voices: list[ElevenLabsVoice],
        default_voice_id: str,
        entry_id: str,
        voice_settings: VoiceSettings,
    ) -> None:
        """Init ElevenLabs TTS service."""
        self._client = client
        self._model = model
        self._default_voice_id = default_voice_id
        self._voices = sorted(
            (Voice(v.voice_id, v.name) for v in voices if v.name),
            key=lambda v: v.name,
        )
        # Default voice first
        voice_indices = [
            idx for idx, v in enumerate(self._voices) if v.voice_id == default_voice_id
        ]
        if voice_indices:
            self._voices.insert(0, self._voices.pop(voice_indices[0]))
        self._voice_settings = voice_settings

        # Entity attributes
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="ElevenLabs",
            model=model.name,
            name="ElevenLabs",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_supported_languages = [
            lang.language_id for lang in self._model.languages or []
        ]
        # Use the first supported language as the default if available
        self._attr_default_language = (
            self._attr_supported_languages[0]
            if self._attr_supported_languages
            else "en"
        )

    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        _LOGGER.debug("Getting TTS audio for %s", message)
        _LOGGER.debug("Options: %s", options)
        voice_id = options.get(ATTR_VOICE, self._default_voice_id)
        model = options.get(ATTR_MODEL, self._model.model_id)
        try:
            audio = self._client.text_to_speech.convert(
                text=message,
                voice_id=voice_id,
                voice_settings=self._voice_settings,
                model_id=model,
            )
            bytes_combined = b"".join([byte_seg async for byte_seg in audio])

        except ApiError as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Generate speech from an incoming message."""
        _LOGGER.debug(
            "Getting TTS audio for language %s and options: %s",
            request.language,
            request.options,
        )
        return TTSAudioResponse("mp3", self._process_tts_stream(request))

    async def _process_tts_stream(
        self, request: TTSAudioRequest
    ) -> AsyncGenerator[bytes]:
        """Generate speech from an incoming message."""
        text_stream = request.message_gen
        boundary_detector = SentenceBoundaryDetector()
        sentences: list[str] = []
        sentences_ready = asyncio.Event()
        sentences_complete = False

        language_code: str | None = request.language
        voice_id = request.options.get(ATTR_VOICE, self._default_voice_id)
        model = request.options.get(ATTR_MODEL, self._model.model_id)

        use_request_ids = model not in MODELS_REQUEST_ID_NOT_SUPPORTED
        previous_request_ids: deque[str] = deque(maxlen=MAX_REQUEST_IDS)
        last_text: str | None = None  # only used for eleven_v3

        base_stream_params = {
            "voice_id": voice_id,
            "model_id": model,
            "output_format": "mp3_44100_128",
            "voice_settings": self._voice_settings,
        }
        if language_code:
            base_stream_params["language_code"] = language_code

        async def _add_sentences() -> None:
            nonlocal sentences_complete

            try:
                # Text chunks may not be on word or sentence boundaries
                async for text_chunk in text_stream:
                    for sentence in boundary_detector.add_chunk(text_chunk):
                        if not sentence.strip():
                            continue

                        sentences.append(sentence)

                    if not sentences:
                        continue

                    sentences_ready.set()

                # Final sentence
                if text := boundary_detector.finish():
                    sentences.append(text)
            finally:
                sentences_complete = True
                sentences_ready.set()

        _add_sentences_task = asyncio.create_task(_add_sentences())

        # Process new sentences as they're available, but synthesize the first
        # one immediately. While that's playing, synthesize (up to) the next 3
        # sentences. After that, synthesize all completed sentences as they're
        # available.
        sentence_schedule = [1, 3]
        while True:
            await sentences_ready.wait()

            if not sentences_complete:
                # Don't wait again if no more sentences are coming
                sentences_ready.clear()

            if not sentences:
                if sentences_complete:
                    # Exit TTS loop
                    _LOGGER.debug("No more sentences to process")
                    break

                # More sentences may be coming
                continue

            new_sentences = sentences[:]
            sentences.clear()

            while new_sentences:
                if sentence_schedule:
                    max_sentences = sentence_schedule.pop(0)
                    sentences_to_process = new_sentences[:max_sentences]
                    new_sentences = new_sentences[len(sentences_to_process) :]
                else:
                    # Process all available sentences together
                    sentences_to_process = new_sentences[:]
                    new_sentences.clear()

                # Combine all new sentences completed to this point
                text = " ".join(sentences_to_process).strip()

                if not text:
                    continue

                # Build kwargs common to both modes
                kwargs = base_stream_params | {
                    "text": text,
                }

                if previous_request_ids:
                    # Send previous request ids.
                    _LOGGER.debug(
                        "Using previous_request_ids for stitching: %s",
                        previous_request_ids,
                    )
                    kwargs["previous_request_ids"] = list(previous_request_ids)
                # Do NOT send previous_text or next_text at all
                elif last_text:
                    # previous_request_ids not supported, send previous_text instead.
                    _LOGGER.debug(
                        "Stitching not supported; using previous_text for continuity: %s",
                        last_text,
                    )
                    kwargs["previous_text"] = last_text

                # Synthesize audio while text chunks are still being accumulated
                _LOGGER.debug("Synthesizing TTS for text: %s", text)
                rid = None
                try:
                    async with self._client.text_to_speech.with_raw_response.stream(
                        **kwargs
                    ) as stream:
                        _LOGGER.debug("Started TTS stream for text: %s", text)
                        async for chunk_bytes in stream.data:
                            yield chunk_bytes

                        _LOGGER.debug("Completed TTS stream for text: %s", text)
                        if use_request_ids:
                            if (rid := stream.headers.get("request-id")) is not None:
                                _LOGGER.debug(
                                    "Storing request-id %s for stitching", rid
                                )
                                previous_request_ids.append(rid)
                            else:
                                _LOGGER.debug(
                                    "No request-id returned from server; clearing previous requests"
                                )
                                previous_request_ids.clear()
                except ApiError as exc:
                    _LOGGER.warning(
                        "Error during processing of TTS request %s", exc, exc_info=True
                    )
                    _add_sentences_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await _add_sentences_task
                    raise HomeAssistantError(exc) from exc

                # Capture and store server request-id for next calls (only when supported)
                _LOGGER.debug("Completed TTS for text: %s", text)
                if not rid:
                    last_text = text

        return
