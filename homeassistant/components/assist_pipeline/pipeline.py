"""Classes for voice assistant pipelines."""

from __future__ import annotations

import array
import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import logging
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import time
from typing import TYPE_CHECKING, Any, Literal, cast
import wave

import hass_nabucasa
import voluptuous as vol

from homeassistant.components import conversation, stt, tts, wake_word, websocket_api
from homeassistant.components.tts import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, MATCH_ALL
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, intent
from homeassistant.helpers.collection import (
    CHANGE_UPDATED,
    CollectionError,
    ItemNotFound,
    SerializedStorageCollection,
    StorageCollection,
    StorageCollectionWebsocket,
)
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType, VolDictType
from homeassistant.util import (
    dt as dt_util,
    language as language_util,
    ulid as ulid_util,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.limited_size_dict import LimitedSizeDict

from .audio_enhancer import AudioEnhancer, EnhancedAudioChunk, MicroVadSpeexEnhancer
from .const import (
    BYTES_PER_CHUNK,
    CONF_DEBUG_RECORDING_DIR,
    DATA_CONFIG,
    DATA_LAST_WAKE_UP,
    DATA_MIGRATIONS,
    DOMAIN,
    MS_PER_CHUNK,
    SAMPLE_CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    SAMPLES_PER_CHUNK,
    WAKE_WORD_COOLDOWN,
)
from .error import (
    DuplicateWakeUpDetectedError,
    IntentRecognitionError,
    PipelineError,
    PipelineNotFound,
    SpeechToTextError,
    TextToSpeechError,
    WakeWordDetectionAborted,
    WakeWordDetectionError,
    WakeWordTimeoutError,
)
from .vad import AudioBuffer, VoiceActivityTimeout, VoiceCommandSegmenter, chunk_samples

if TYPE_CHECKING:
    from hassil.recognize import RecognizeResult

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.pipelines"
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2

ENGINE_LANGUAGE_PAIRS = (
    ("stt_engine", "stt_language"),
    ("tts_engine", "tts_language"),
)

KEY_ASSIST_PIPELINE: HassKey[PipelineData] = HassKey(DOMAIN)
KEY_PIPELINE_CONVERSATION_DATA: HassKey[dict[str, PipelineConversationData]] = HassKey(
    "pipeline_conversation_data"
)


def validate_language(data: dict[str, Any]) -> Any:
    """Validate language settings."""
    for engine, language in ENGINE_LANGUAGE_PAIRS:
        if data[engine] is not None and data[language] is None:
            raise vol.Invalid(f"Need language {language} for {engine} {data[engine]}")
    return data


PIPELINE_FIELDS: VolDictType = {
    vol.Required("conversation_engine"): str,
    vol.Required("conversation_language"): str,
    vol.Required("language"): str,
    vol.Required("name"): str,
    vol.Required("stt_engine"): vol.Any(str, None),
    vol.Required("stt_language"): vol.Any(str, None),
    vol.Required("tts_engine"): vol.Any(str, None),
    vol.Required("tts_language"): vol.Any(str, None),
    vol.Required("tts_voice"): vol.Any(str, None),
    vol.Required("wake_word_entity"): vol.Any(str, None),
    vol.Required("wake_word_id"): vol.Any(str, None),
    vol.Optional("prefer_local_intents"): bool,
}

STORED_PIPELINE_RUNS = 10

SAVE_DELAY = 10


@callback
def _async_local_fallback_intent_filter(result: RecognizeResult) -> bool:
    """Filter out intents that are not local fallback."""
    return result.intent.name in (intent.INTENT_GET_STATE)


@callback
def _async_resolve_default_pipeline_settings(
    hass: HomeAssistant,
    *,
    conversation_engine_id: str | None = None,
    stt_engine_id: str | None = None,
    tts_engine_id: str | None = None,
    pipeline_name: str,
) -> dict[str, str | None]:
    """Resolve settings for a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines if none are specified.
    """
    conversation_language = "en"
    pipeline_language = "en"
    stt_engine = None
    stt_language = None
    tts_engine = None
    tts_language = None
    tts_voice = None
    wake_word_entity = None
    wake_word_id = None

    if conversation_engine_id is None:
        conversation_engine_id = conversation.HOME_ASSISTANT_AGENT

    # Find a matching language supported by the Home Assistant conversation agent
    conversation_languages = language_util.matches(
        hass.config.language,
        conversation.async_get_conversation_languages(hass, conversation_engine_id),
        country=hass.config.country,
    )
    if conversation_languages:
        pipeline_language = hass.config.language
        conversation_language = conversation_languages[0]

    if stt_engine_id is None:
        stt_engine_id = stt.async_default_engine(hass)

    if stt_engine_id is not None:
        stt_engine = stt.async_get_speech_to_text_engine(hass, stt_engine_id)
        if stt_engine is None:
            stt_engine_id = None

    if stt_engine:
        stt_languages = language_util.matches(
            pipeline_language,
            stt_engine.supported_languages,
            country=hass.config.country,
        )
        if stt_languages:
            stt_language = stt_languages[0]
        else:
            _LOGGER.debug(
                "Speech-to-text engine '%s' does not support language '%s'",
                stt_engine_id,
                pipeline_language,
            )
            stt_engine_id = None

    if tts_engine_id is None:
        tts_engine_id = tts.async_default_engine(hass)

    if tts_engine_id is not None:
        tts_engine = tts.get_engine_instance(hass, tts_engine_id)
        if tts_engine is None:
            tts_engine_id = None

    if tts_engine:
        tts_languages = language_util.matches(
            pipeline_language,
            tts_engine.supported_languages,
            country=hass.config.country,
        )
        if tts_languages:
            tts_language = tts_languages[0]
            tts_voices = tts_engine.async_get_supported_voices(tts_language)
            if tts_voices:
                tts_voice = tts_voices[0].voice_id
        else:
            _LOGGER.debug(
                "Text-to-speech engine '%s' does not support language '%s'",
                tts_engine_id,
                pipeline_language,
            )
            tts_engine_id = None

    return {
        "conversation_engine": conversation_engine_id,
        "conversation_language": conversation_language,
        "language": hass.config.language,
        "name": pipeline_name,
        "stt_engine": stt_engine_id,
        "stt_language": stt_language,
        "tts_engine": tts_engine_id,
        "tts_language": tts_language,
        "tts_voice": tts_voice,
        "wake_word_entity": wake_word_entity,
        "wake_word_id": wake_word_id,
    }


async def _async_create_default_pipeline(
    hass: HomeAssistant, pipeline_store: PipelineStorageCollection
) -> Pipeline:
    """Create a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines.
    """
    pipeline_settings = _async_resolve_default_pipeline_settings(
        hass, pipeline_name="Home Assistant"
    )
    return await pipeline_store.async_create_item(pipeline_settings)


async def async_create_default_pipeline(
    hass: HomeAssistant,
    stt_engine_id: str,
    tts_engine_id: str,
    pipeline_name: str,
) -> Pipeline | None:
    """Create a pipeline with default settings.

    The default pipeline will use the homeassistant conversation agent and the
    specified stt / tts engines.
    """
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]
    pipeline_store = pipeline_data.pipeline_store
    pipeline_settings = _async_resolve_default_pipeline_settings(
        hass,
        stt_engine_id=stt_engine_id,
        tts_engine_id=tts_engine_id,
        pipeline_name=pipeline_name,
    )
    if (
        pipeline_settings["stt_engine"] != stt_engine_id
        or pipeline_settings["tts_engine"] != tts_engine_id
    ):
        return None
    return await pipeline_store.async_create_item(pipeline_settings)


@callback
def _async_get_pipeline_from_conversation_entity(
    hass: HomeAssistant, entity_id: str
) -> Pipeline:
    """Get a pipeline by conversation entity ID."""
    entity = hass.states.get(entity_id)
    settings = _async_resolve_default_pipeline_settings(
        hass,
        pipeline_name=entity.name if entity else entity_id,
        conversation_engine_id=entity_id,
    )
    settings["id"] = entity_id

    return Pipeline.from_json(settings)


@callback
def async_get_pipeline(hass: HomeAssistant, pipeline_id: str | None = None) -> Pipeline:
    """Get a pipeline by id or the preferred pipeline."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    if pipeline_id is None:
        # A pipeline was not specified, use the preferred one
        pipeline_id = pipeline_data.pipeline_store.async_get_preferred_item()

    if pipeline_id.startswith("conversation."):
        return _async_get_pipeline_from_conversation_entity(hass, pipeline_id)

    pipeline = pipeline_data.pipeline_store.data.get(pipeline_id)

    # If invalid pipeline ID was specified
    if pipeline is None:
        raise PipelineNotFound(
            "pipeline_not_found", f"Pipeline {pipeline_id} not found"
        )

    return pipeline


@callback
def async_get_pipelines(hass: HomeAssistant) -> list[Pipeline]:
    """Get all pipelines."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    return list(pipeline_data.pipeline_store.data.values())


async def async_update_pipeline(
    hass: HomeAssistant,
    pipeline: Pipeline,
    *,
    conversation_engine: str | UndefinedType = UNDEFINED,
    conversation_language: str | UndefinedType = UNDEFINED,
    language: str | UndefinedType = UNDEFINED,
    name: str | UndefinedType = UNDEFINED,
    stt_engine: str | None | UndefinedType = UNDEFINED,
    stt_language: str | None | UndefinedType = UNDEFINED,
    tts_engine: str | None | UndefinedType = UNDEFINED,
    tts_language: str | None | UndefinedType = UNDEFINED,
    tts_voice: str | None | UndefinedType = UNDEFINED,
    wake_word_entity: str | None | UndefinedType = UNDEFINED,
    wake_word_id: str | None | UndefinedType = UNDEFINED,
    prefer_local_intents: bool | UndefinedType = UNDEFINED,
) -> None:
    """Update a pipeline."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    updates: dict[str, Any] = pipeline.to_json()
    updates.pop("id")
    # Refactor this once we bump to Python 3.12
    # and have https://peps.python.org/pep-0692/
    updates.update(
        {
            key: val
            for key, val in (
                ("conversation_engine", conversation_engine),
                ("conversation_language", conversation_language),
                ("language", language),
                ("name", name),
                ("stt_engine", stt_engine),
                ("stt_language", stt_language),
                ("tts_engine", tts_engine),
                ("tts_language", tts_language),
                ("tts_voice", tts_voice),
                ("wake_word_entity", wake_word_entity),
                ("wake_word_id", wake_word_id),
                ("prefer_local_intents", prefer_local_intents),
            )
            if val is not UNDEFINED
        }
    )

    await pipeline_data.pipeline_store.async_update_item(pipeline.id, updates)


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_END = "run-end"
    WAKE_WORD_START = "wake_word-start"
    WAKE_WORD_END = "wake_word-end"
    STT_START = "stt-start"
    STT_VAD_START = "stt-vad-start"
    STT_VAD_END = "stt-vad-end"
    STT_END = "stt-end"
    INTENT_START = "intent-start"
    INTENT_PROGRESS = "intent-progress"
    INTENT_END = "intent-end"
    TTS_START = "tts-start"
    TTS_END = "tts-end"
    ERROR = "error"


@dataclass(frozen=True)
class PipelineEvent:
    """Events emitted during a pipeline run."""

    type: PipelineEventType
    data: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: dt_util.utcnow().isoformat())


type PipelineEventCallback = Callable[[PipelineEvent], None]


@dataclass(frozen=True)
class Pipeline:
    """A voice assistant pipeline."""

    conversation_engine: str
    conversation_language: str
    language: str
    name: str
    stt_engine: str | None
    stt_language: str | None
    tts_engine: str | None
    tts_language: str | None
    tts_voice: str | None
    wake_word_entity: str | None
    wake_word_id: str | None
    prefer_local_intents: bool = False

    id: str = field(default_factory=ulid_util.ulid_now)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Pipeline:
        """Create an instance from a JSON serialization.

        This function was added in HA Core 2023.10, previous versions will raise
        if there are unexpected items in the serialized data.
        """
        return cls(
            conversation_engine=data["conversation_engine"],
            conversation_language=data["conversation_language"],
            id=data["id"],
            language=data["language"],
            name=data["name"],
            stt_engine=data["stt_engine"],
            stt_language=data["stt_language"],
            tts_engine=data["tts_engine"],
            tts_language=data["tts_language"],
            tts_voice=data["tts_voice"],
            wake_word_entity=data["wake_word_entity"],
            wake_word_id=data["wake_word_id"],
            prefer_local_intents=data.get("prefer_local_intents", False),
        )

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "conversation_engine": self.conversation_engine,
            "conversation_language": self.conversation_language,
            "id": self.id,
            "language": self.language,
            "name": self.name,
            "stt_engine": self.stt_engine,
            "stt_language": self.stt_language,
            "tts_engine": self.tts_engine,
            "tts_language": self.tts_language,
            "tts_voice": self.tts_voice,
            "wake_word_entity": self.wake_word_entity,
            "wake_word_id": self.wake_word_id,
            "prefer_local_intents": self.prefer_local_intents,
        }


class PipelineStage(StrEnum):
    """Stages of a pipeline."""

    WAKE_WORD = "wake_word"
    STT = "stt"
    INTENT = "intent"
    TTS = "tts"
    END = "end"


PIPELINE_STAGE_ORDER = [
    PipelineStage.WAKE_WORD,
    PipelineStage.STT,
    PipelineStage.INTENT,
    PipelineStage.TTS,
]


class PipelineRunValidationError(Exception):
    """Error when a pipeline run is not valid."""


class InvalidPipelineStagesError(PipelineRunValidationError):
    """Error when given an invalid combination of start/end stages."""

    def __init__(
        self,
        start_stage: PipelineStage,
        end_stage: PipelineStage,
    ) -> None:
        """Set error message."""
        super().__init__(
            f"Invalid stage combination: start={start_stage}, end={end_stage}"
        )


@dataclass(frozen=True)
class WakeWordSettings:
    """Settings for wake word detection."""

    timeout: float | None = None
    """Seconds of silence before detection times out."""

    audio_seconds_to_buffer: float = 0
    """Seconds of audio to buffer before detection and forward to STT."""


@dataclass(frozen=True)
class AudioSettings:
    """Settings for pipeline audio processing."""

    noise_suppression_level: int = 0
    """Level of noise suppression (0 = disabled, 4 = max)"""

    auto_gain_dbfs: int = 0
    """Amount of automatic gain in dbFS (0 = disabled, 31 = max)"""

    volume_multiplier: float = 1.0
    """Multiplier used directly on PCM samples (1.0 = no change, 2.0 = twice as loud)"""

    is_vad_enabled: bool = True
    """True if VAD is used to determine the end of the voice command."""

    silence_seconds: float = 0.7
    """Seconds of silence after voice command has ended."""

    def __post_init__(self) -> None:
        """Verify settings post-initialization."""
        if (self.noise_suppression_level < 0) or (self.noise_suppression_level > 4):
            raise ValueError("noise_suppression_level must be in [0, 4]")

        if (self.auto_gain_dbfs < 0) or (self.auto_gain_dbfs > 31):
            raise ValueError("auto_gain_dbfs must be in [0, 31]")

    @property
    def needs_processor(self) -> bool:
        """True if an audio processor is needed."""
        return (
            self.is_vad_enabled
            or (self.noise_suppression_level > 0)
            or (self.auto_gain_dbfs > 0)
        )


@dataclass
class PipelineRun:
    """Running context for a pipeline."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    start_stage: PipelineStage
    end_stage: PipelineStage
    event_callback: PipelineEventCallback
    language: str = None  # type: ignore[assignment]
    runner_data: Any | None = None
    intent_agent: str | None = None
    tts_audio_output: str | dict[str, Any] | None = None
    wake_word_settings: WakeWordSettings | None = None
    audio_settings: AudioSettings = field(default_factory=AudioSettings)

    id: str = field(default_factory=ulid_util.ulid_now)
    stt_provider: stt.SpeechToTextEntity | stt.Provider = field(init=False, repr=False)
    tts_stream: tts.ResultStream | None = field(init=False, default=None)
    wake_word_entity_id: str | None = field(init=False, default=None, repr=False)
    wake_word_entity: wake_word.WakeWordDetectionEntity = field(init=False, repr=False)

    abort_wake_word_detection: bool = field(init=False, default=False)

    debug_recording_thread: Thread | None = None
    """Thread that records audio to debug_recording_dir"""

    debug_recording_queue: Queue[str | bytes | None] | None = None
    """Queue to communicate with debug recording thread"""

    audio_enhancer: AudioEnhancer | None = None
    """VAD/noise suppression/auto gain"""

    audio_chunking_buffer: AudioBuffer = field(
        default_factory=lambda: AudioBuffer(BYTES_PER_CHUNK)
    )
    """Buffer used when splitting audio into chunks for audio processing"""

    _device_id: str | None = None
    """Optional device id set during run start."""

    _conversation_data: PipelineConversationData | None = None
    """Data tied to the conversation ID."""

    _intent_agent_only = False
    """If request should only be handled by agent, ignoring sentence triggers and local processing."""

    def __post_init__(self) -> None:
        """Set language for pipeline."""
        self.language = self.pipeline.language or self.hass.config.language

        # wake -> stt -> intent -> tts
        if PIPELINE_STAGE_ORDER.index(self.end_stage) < PIPELINE_STAGE_ORDER.index(
            self.start_stage
        ):
            raise InvalidPipelineStagesError(self.start_stage, self.end_stage)

        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        if self.pipeline.id not in pipeline_data.pipeline_debug:
            pipeline_data.pipeline_debug[self.pipeline.id] = LimitedSizeDict(
                size_limit=STORED_PIPELINE_RUNS
            )
        pipeline_data.pipeline_debug[self.pipeline.id][self.id] = PipelineRunDebug()
        pipeline_data.pipeline_runs.add_run(self)

        # Initialize with audio settings
        if self.audio_settings.needs_processor and (self.audio_enhancer is None):
            # Default audio enhancer
            self.audio_enhancer = MicroVadSpeexEnhancer(
                self.audio_settings.auto_gain_dbfs,
                self.audio_settings.noise_suppression_level,
                self.audio_settings.is_vad_enabled,
            )

    def __eq__(self, other: object) -> bool:
        """Compare pipeline runs by id."""
        if isinstance(other, PipelineRun):
            return self.id == other.id

        return False

    @callback
    def process_event(self, event: PipelineEvent) -> None:
        """Log an event and call listener."""
        self.event_callback(event)
        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        if self.id not in pipeline_data.pipeline_debug[self.pipeline.id]:
            # This run has been evicted from the logged pipeline runs already
            return
        pipeline_data.pipeline_debug[self.pipeline.id][self.id].events.append(event)

    def start(self, conversation_id: str, device_id: str | None) -> None:
        """Emit run start event."""
        self._device_id = device_id
        self._start_debug_recording_thread()

        data: dict[str, Any] = {
            "pipeline": self.pipeline.id,
            "language": self.language,
            "conversation_id": conversation_id,
        }
        if self.runner_data is not None:
            data["runner_data"] = self.runner_data
        if self.tts_stream:
            data["tts_output"] = {
                "token": self.tts_stream.token,
                "url": self.tts_stream.url,
                "mime_type": self.tts_stream.content_type,
            }

        self.process_event(PipelineEvent(PipelineEventType.RUN_START, data))

    async def end(self) -> None:
        """Emit run end event."""
        # Signal end of stream to listeners
        self._capture_chunk(None)

        # Stop the recording thread before emitting run-end.
        # This ensures that files are properly closed if the event handler reads them.
        await self._stop_debug_recording_thread()

        self.process_event(
            PipelineEvent(
                PipelineEventType.RUN_END,
            )
        )

        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        pipeline_data.pipeline_runs.remove_run(self)

    async def prepare_wake_word_detection(self) -> None:
        """Prepare wake-word-detection."""
        entity_id = self.pipeline.wake_word_entity or wake_word.async_default_entity(
            self.hass
        )
        if entity_id is None:
            raise WakeWordDetectionError(
                code="wake-engine-missing",
                message="No wake word engine",
            )

        wake_word_entity = wake_word.async_get_wake_word_detection_entity(
            self.hass, entity_id
        )
        if wake_word_entity is None:
            raise WakeWordDetectionError(
                code="wake-provider-missing",
                message=f"No wake-word-detection provider for: {entity_id}",
            )

        self.wake_word_entity_id = entity_id
        self.wake_word_entity = wake_word_entity

    async def wake_word_detection(
        self,
        stream: AsyncIterable[EnhancedAudioChunk],
        audio_chunks_for_stt: list[EnhancedAudioChunk],
    ) -> wake_word.DetectionResult | None:
        """Run wake-word-detection portion of pipeline. Returns detection result."""
        metadata_dict = asdict(
            stt.SpeechMetadata(
                language="",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            )
        )

        wake_word_settings = self.wake_word_settings or WakeWordSettings()

        # Remove language since it doesn't apply to wake words yet
        metadata_dict.pop("language", None)

        self.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_START,
                {
                    "entity_id": self.wake_word_entity_id,
                    "metadata": metadata_dict,
                    "timeout": wake_word_settings.timeout or 0,
                },
            )
        )

        if self.debug_recording_queue is not None:
            self.debug_recording_queue.put_nowait(f"00_wake-{self.wake_word_entity_id}")

        wake_word_vad: VoiceActivityTimeout | None = None
        if (wake_word_settings.timeout is not None) and (
            wake_word_settings.timeout > 0
        ):
            # Use VAD to determine timeout
            wake_word_vad = VoiceActivityTimeout(wake_word_settings.timeout)

        # Audio chunk buffer. This audio will be forwarded to speech-to-text
        # after wake-word-detection.
        num_audio_chunks_to_buffer = int(
            (wake_word_settings.audio_seconds_to_buffer * SAMPLE_RATE)
            / SAMPLES_PER_CHUNK
        )

        stt_audio_buffer: deque[EnhancedAudioChunk] | None = None
        if num_audio_chunks_to_buffer > 0:
            stt_audio_buffer = deque(maxlen=num_audio_chunks_to_buffer)

        try:
            # Detect wake word(s)
            result = await self.wake_word_entity.async_process_audio_stream(
                self._wake_word_audio_stream(
                    audio_stream=stream,
                    stt_audio_buffer=stt_audio_buffer,
                    wake_word_vad=wake_word_vad,
                ),
                self.pipeline.wake_word_id,
            )

            if stt_audio_buffer is not None:
                # All audio kept from right before the wake word was detected as
                # a single chunk.
                audio_chunks_for_stt.extend(stt_audio_buffer)
        except WakeWordDetectionAborted:
            raise
        except WakeWordTimeoutError:
            _LOGGER.debug("Timeout during wake word detection")
            raise
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during wake-word-detection")
            raise WakeWordDetectionError(
                code="wake-stream-failed",
                message="Unexpected error during wake-word-detection",
            ) from src_error

        _LOGGER.debug("wake-word-detection result %s", result)

        if result is None:
            wake_word_output: dict[str, Any] = {}
        else:
            # Avoid duplicate detections by checking cooldown
            last_wake_up = self.hass.data[DATA_LAST_WAKE_UP].get(
                result.wake_word_phrase
            )
            if last_wake_up is not None:
                sec_since_last_wake_up = time.monotonic() - last_wake_up
                if sec_since_last_wake_up < WAKE_WORD_COOLDOWN:
                    _LOGGER.debug(
                        "Duplicate wake word detection occurred for %s",
                        result.wake_word_phrase,
                    )
                    raise DuplicateWakeUpDetectedError(result.wake_word_phrase)

            # Record last wake up time to block duplicate detections
            self.hass.data[DATA_LAST_WAKE_UP][result.wake_word_phrase] = (
                time.monotonic()
            )

            if result.queued_audio:
                # Add audio that was pending at detection.
                #
                # Because detection occurs *after* the wake word was actually
                # spoken, we need to make sure pending audio is forwarded to
                # speech-to-text so the user does not have to pause before
                # speaking the voice command.
                audio_chunks_for_stt.extend(
                    EnhancedAudioChunk(
                        audio=chunk_ts[0],
                        timestamp_ms=chunk_ts[1],
                        speech_probability=None,
                    )
                    for chunk_ts in result.queued_audio
                )

            wake_word_output = asdict(result)

            # Remove non-JSON fields
            wake_word_output.pop("queued_audio", None)

        self.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_END,
                {"wake_word_output": wake_word_output},
            )
        )

        return result

    async def _wake_word_audio_stream(
        self,
        audio_stream: AsyncIterable[EnhancedAudioChunk],
        stt_audio_buffer: deque[EnhancedAudioChunk] | None,
        wake_word_vad: VoiceActivityTimeout | None,
        sample_rate: int = SAMPLE_RATE,
        sample_width: int = SAMPLE_WIDTH,
    ) -> AsyncIterable[tuple[bytes, int]]:
        """Yield audio chunks with timestamps (milliseconds since start of stream).

        Adds audio to a ring buffer that will be forwarded to speech-to-text after
        detection. Times out if VAD detects enough silence.
        """
        async for chunk in audio_stream:
            if self.abort_wake_word_detection:
                raise WakeWordDetectionAborted

            self._capture_chunk(chunk.audio)
            yield chunk.audio, chunk.timestamp_ms

            # Wake-word-detection occurs *after* the wake word was actually
            # spoken. Keeping audio right before detection allows the voice
            # command to be spoken immediately after the wake word.
            if stt_audio_buffer is not None:
                stt_audio_buffer.append(chunk)

            if wake_word_vad is not None:
                chunk_seconds = (len(chunk.audio) // sample_width) / sample_rate
                if not wake_word_vad.process(chunk_seconds, chunk.speech_probability):
                    raise WakeWordTimeoutError(
                        code="wake-word-timeout", message="Wake word was not detected"
                    )

    async def prepare_speech_to_text(self, metadata: stt.SpeechMetadata) -> None:
        """Prepare speech-to-text."""
        # pipeline.stt_engine can't be None or this function is not called
        stt_provider = stt.async_get_speech_to_text_engine(
            self.hass,
            self.pipeline.stt_engine,  # type: ignore[arg-type]
        )

        if stt_provider is None:
            engine = self.pipeline.stt_engine
            raise SpeechToTextError(
                code="stt-provider-missing",
                message=f"No speech-to-text provider for: {engine}",
            )

        metadata.language = self.pipeline.stt_language or self.language

        if not stt_provider.check_metadata(metadata):
            raise SpeechToTextError(
                code="stt-provider-unsupported-metadata",
                message=(
                    f"Provider {stt_provider.name} does not support input speech "
                    f"to text metadata {metadata}"
                ),
            )

        self.stt_provider = stt_provider

    async def speech_to_text(
        self,
        metadata: stt.SpeechMetadata,
        stream: AsyncIterable[EnhancedAudioChunk],
    ) -> str:
        """Run speech-to-text portion of pipeline. Returns the spoken text."""
        # Create a background task to prepare the conversation agent
        if self.end_stage >= PipelineStage.INTENT:
            self.hass.async_create_background_task(
                conversation.async_prepare_agent(
                    self.hass, self.intent_agent, self.language
                ),
                f"prepare conversation agent {self.intent_agent}",
            )

        if isinstance(self.stt_provider, stt.Provider):
            engine = self.stt_provider.name
        else:
            engine = self.stt_provider.entity_id

        self.process_event(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": engine,
                    "metadata": asdict(metadata),
                },
            )
        )

        if self.debug_recording_queue is not None:
            # New recording
            self.debug_recording_queue.put_nowait(f"01_stt-{engine}")

        try:
            # Transcribe audio stream
            stt_vad: VoiceCommandSegmenter | None = None
            if self.audio_settings.is_vad_enabled:
                stt_vad = VoiceCommandSegmenter(
                    silence_seconds=self.audio_settings.silence_seconds
                )

            result = await self.stt_provider.async_process_audio_stream(
                metadata,
                self._speech_to_text_stream(audio_stream=stream, stt_vad=stt_vad),
            )
        except (asyncio.CancelledError, TimeoutError):
            raise  # expected
        except hass_nabucasa.auth.Unauthenticated as src_error:
            raise SpeechToTextError(
                code="cloud-auth-failed",
                message="Home Assistant Cloud authentication failed",
            ) from src_error
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during speech-to-text")
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="Unexpected error during speech-to-text",
            ) from src_error

        _LOGGER.debug("speech-to-text result %s", result)

        if result.result != stt.SpeechResultState.SUCCESS:
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="speech-to-text failed",
            )

        if not result.text:
            raise SpeechToTextError(
                code="stt-no-text-recognized", message="No text recognized"
            )

        self.process_event(
            PipelineEvent(
                PipelineEventType.STT_END,
                {
                    "stt_output": {
                        "text": result.text,
                    }
                },
            )
        )

        return result.text

    async def _speech_to_text_stream(
        self,
        audio_stream: AsyncIterable[EnhancedAudioChunk],
        stt_vad: VoiceCommandSegmenter | None,
        sample_rate: int = SAMPLE_RATE,
        sample_width: int = SAMPLE_WIDTH,
    ) -> AsyncGenerator[bytes]:
        """Yield audio chunks until VAD detects silence or speech-to-text completes."""
        sent_vad_start = False
        async for chunk in audio_stream:
            self._capture_chunk(chunk.audio)

            if stt_vad is not None:
                chunk_seconds = (len(chunk.audio) // sample_width) / sample_rate
                if not stt_vad.process(chunk_seconds, chunk.speech_probability):
                    # Silence detected at the end of voice command
                    self.process_event(
                        PipelineEvent(
                            PipelineEventType.STT_VAD_END,
                            {"timestamp": chunk.timestamp_ms},
                        )
                    )
                    break

                if stt_vad.in_command and (not sent_vad_start):
                    # Speech detected at start of voice command
                    self.process_event(
                        PipelineEvent(
                            PipelineEventType.STT_VAD_START,
                            {"timestamp": chunk.timestamp_ms},
                        )
                    )
                    sent_vad_start = True

            yield chunk.audio

    async def prepare_recognize_intent(self, session: chat_session.ChatSession) -> None:
        """Prepare recognizing an intent."""
        self._conversation_data = async_get_pipeline_conversation_data(
            self.hass, session
        )

        if self._conversation_data.continue_conversation_agent is not None:
            agent_info = conversation.async_get_agent_info(
                self.hass, self._conversation_data.continue_conversation_agent
            )
            self._conversation_data.continue_conversation_agent = None
            if agent_info is None:
                raise IntentRecognitionError(
                    code="intent-agent-not-found",
                    message=f"Intent recognition engine {self._conversation_data.continue_conversation_agent} asked for follow-up but is no longer found",
                )
            self._intent_agent_only = True

        else:
            agent_info = conversation.async_get_agent_info(
                self.hass,
                self.pipeline.conversation_engine or conversation.HOME_ASSISTANT_AGENT,
            )

            if agent_info is None:
                engine = self.pipeline.conversation_engine or "default"
                raise IntentRecognitionError(
                    code="intent-not-supported",
                    message=f"Intent recognition engine {engine} is not found",
                )

        self.intent_agent = agent_info.id

    async def recognize_intent(
        self,
        intent_input: str,
        conversation_id: str,
        device_id: str | None,
        conversation_extra_system_prompt: str | None,
    ) -> str:
        """Run intent recognition portion of pipeline. Returns text to speak."""
        if self.intent_agent is None or self._conversation_data is None:
            raise RuntimeError("Recognize intent was not prepared")

        if self.pipeline.conversation_language == MATCH_ALL:
            # LLMs support all languages ('*') so use languages from the
            # pipeline for intent fallback.
            #
            # We prioritize the STT and TTS languages because they may be more
            # specific, such as "zh-CN" instead of just "zh". This is necessary
            # for languages whose intents are split out by region when
            # preferring local intent matching.
            input_language = (
                self.pipeline.stt_language
                or self.pipeline.tts_language
                or self.pipeline.language
            )
        else:
            input_language = self.pipeline.conversation_language

        self.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.intent_agent,
                    "language": input_language,
                    "intent_input": intent_input,
                    "conversation_id": conversation_id,
                    "device_id": device_id,
                    "prefer_local_intents": self.pipeline.prefer_local_intents,
                },
            )
        )

        try:
            user_input = conversation.ConversationInput(
                text=intent_input,
                context=self.context,
                conversation_id=conversation_id,
                device_id=device_id,
                language=input_language,
                agent_id=self.intent_agent,
                extra_system_prompt=conversation_extra_system_prompt,
            )

            agent_id = self.intent_agent
            processed_locally = agent_id == conversation.HOME_ASSISTANT_AGENT
            intent_response: intent.IntentResponse | None = None
            if not processed_locally and not self._intent_agent_only:
                # Sentence triggers override conversation agent
                if (
                    trigger_response_text
                    := await conversation.async_handle_sentence_triggers(
                        self.hass, user_input
                    )
                ) is not None:
                    # Sentence trigger matched
                    agent_id = "sentence_trigger"
                    intent_response = intent.IntentResponse(
                        self.pipeline.conversation_language
                    )
                    intent_response.async_set_speech(trigger_response_text)

                intent_filter: Callable[[RecognizeResult], bool] | None = None
                # If the LLM has API access, we filter out some sentences that are
                # interfering with LLM operation.
                if (
                    intent_agent_state := self.hass.states.get(self.intent_agent)
                ) and intent_agent_state.attributes.get(
                    ATTR_SUPPORTED_FEATURES, 0
                ) & conversation.ConversationEntityFeature.CONTROL:
                    intent_filter = _async_local_fallback_intent_filter

                # Try local intents
                if (
                    intent_response is None
                    and self.pipeline.prefer_local_intents
                    and (
                        intent_response := await conversation.async_handle_intents(
                            self.hass,
                            user_input,
                            intent_filter=intent_filter,
                        )
                    )
                ):
                    # Local intent matched
                    agent_id = conversation.HOME_ASSISTANT_AGENT
                    processed_locally = True

            @callback
            def chat_log_delta_listener(
                chat_log: conversation.ChatLog, delta: dict
            ) -> None:
                """Handle chat log delta."""
                self.process_event(
                    PipelineEvent(
                        PipelineEventType.INTENT_PROGRESS,
                        {
                            "chat_log_delta": delta,
                        },
                    )
                )

            with (
                chat_session.async_get_chat_session(
                    self.hass, user_input.conversation_id
                ) as session,
                conversation.async_get_chat_log(
                    self.hass,
                    session,
                    user_input,
                    chat_log_delta_listener=chat_log_delta_listener,
                ) as chat_log,
            ):
                # It was already handled, create response and add to chat history
                if intent_response is not None:
                    speech: str = intent_response.speech.get("plain", {}).get(
                        "speech", ""
                    )
                    chat_log.async_add_assistant_content_without_tools(
                        conversation.AssistantContent(
                            agent_id=agent_id,
                            content=speech,
                        )
                    )
                    conversation_result = conversation.ConversationResult(
                        response=intent_response,
                        conversation_id=session.conversation_id,
                    )

                else:
                    # Fall back to pipeline conversation agent
                    conversation_result = await conversation.async_converse(
                        hass=self.hass,
                        text=user_input.text,
                        conversation_id=user_input.conversation_id,
                        device_id=user_input.device_id,
                        context=user_input.context,
                        language=user_input.language,
                        agent_id=user_input.agent_id,
                        extra_system_prompt=user_input.extra_system_prompt,
                    )
                    speech = conversation_result.response.speech.get("plain", {}).get(
                        "speech", ""
                    )

        except Exception as src_error:
            _LOGGER.exception("Unexpected error during intent recognition")
            raise IntentRecognitionError(
                code="intent-failed",
                message="Unexpected error during intent recognition",
            ) from src_error

        _LOGGER.debug("conversation result %s", conversation_result)

        self.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_END,
                {
                    "processed_locally": processed_locally,
                    "intent_output": conversation_result.as_dict(),
                },
            )
        )

        if conversation_result.continue_conversation:
            self._conversation_data.continue_conversation_agent = agent_id

        return speech

    async def prepare_text_to_speech(self) -> None:
        """Prepare text-to-speech."""
        # pipeline.tts_engine can't be None or this function is not called
        engine = cast(str, self.pipeline.tts_engine)

        tts_options: dict[str, Any] = {}
        if self.pipeline.tts_voice is not None:
            tts_options[tts.ATTR_VOICE] = self.pipeline.tts_voice

        if isinstance(self.tts_audio_output, dict):
            tts_options.update(self.tts_audio_output)
        elif isinstance(self.tts_audio_output, str):
            tts_options[tts.ATTR_PREFERRED_FORMAT] = self.tts_audio_output
            if self.tts_audio_output == "wav":
                # 16 Khz, 16-bit mono
                tts_options[tts.ATTR_PREFERRED_SAMPLE_RATE] = SAMPLE_RATE
                tts_options[tts.ATTR_PREFERRED_SAMPLE_CHANNELS] = SAMPLE_CHANNELS
                tts_options[tts.ATTR_PREFERRED_SAMPLE_BYTES] = SAMPLE_WIDTH

        try:
            self.tts_stream = tts.async_create_stream(
                hass=self.hass,
                engine=engine,
                language=self.pipeline.tts_language,
                options=tts_options,
            )
        except HomeAssistantError as err:
            raise TextToSpeechError(
                code="tts-not-supported",
                message=(
                    f"Text-to-speech engine {engine} "
                    f"does not support language {self.pipeline.tts_language} or options {tts_options}:"
                    f" {err}"
                ),
            ) from err

    async def text_to_speech(self, tts_input: str) -> None:
        """Run text-to-speech portion of pipeline."""
        assert self.tts_stream is not None

        self.process_event(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.tts_stream.engine,
                    "language": self.pipeline.tts_language,
                    "voice": self.pipeline.tts_voice,
                    "tts_input": tts_input,
                },
            )
        )

        try:
            # Synthesize audio and get URL
            tts_media_id = tts_generate_media_source_id(
                self.hass,
                tts_input,
                engine=self.tts_stream.engine,
                language=self.tts_stream.language,
                options=self.tts_stream.options,
            )
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during text-to-speech")
            raise TextToSpeechError(
                code="tts-failed",
                message="Unexpected error during text-to-speech",
            ) from src_error

        self.tts_stream.async_set_message(tts_input)

        tts_output = {
            "media_id": tts_media_id,
            "token": self.tts_stream.token,
            "url": self.tts_stream.url,
            "mime_type": self.tts_stream.content_type,
        }

        self.process_event(
            PipelineEvent(PipelineEventType.TTS_END, {"tts_output": tts_output})
        )

    def _capture_chunk(self, audio_bytes: bytes | None) -> None:
        """Forward audio chunk to various capturing mechanisms."""
        if self.debug_recording_queue is not None:
            # Forward to debug WAV file recording
            self.debug_recording_queue.put_nowait(audio_bytes)

        if self._device_id is None:
            return

        # Forward to device audio capture
        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        audio_queue = pipeline_data.device_audio_queues.get(self._device_id)
        if audio_queue is None:
            return

        try:
            audio_queue.queue.put_nowait(audio_bytes)
        except asyncio.QueueFull:
            audio_queue.overflow = True
            _LOGGER.warning("Audio queue full for device %s", self._device_id)

    def _start_debug_recording_thread(self) -> None:
        """Start thread to record wake/stt audio if debug_recording_dir is set."""
        if self.debug_recording_thread is not None:
            # Already started
            return

        # Directory to save audio for each pipeline run.
        # Configured in YAML for assist_pipeline.
        if debug_recording_dir := self.hass.data[DATA_CONFIG].get(
            CONF_DEBUG_RECORDING_DIR
        ):
            if self._device_id is None:
                # <debug_recording_dir>/<pipeline.name>/<run.id>
                run_recording_dir = (
                    Path(debug_recording_dir)
                    / self.pipeline.name
                    / str(time.monotonic_ns())
                )
            else:
                # <debug_recording_dir>/<device_id>/<pipeline.name>/<run.id>
                run_recording_dir = (
                    Path(debug_recording_dir)
                    / self._device_id
                    / self.pipeline.name
                    / str(time.monotonic_ns())
                )

            self.debug_recording_queue = Queue()
            self.debug_recording_thread = Thread(
                target=_pipeline_debug_recording_thread_proc,
                args=(run_recording_dir, self.debug_recording_queue),
                daemon=True,
            )
            self.debug_recording_thread.start()

    async def _stop_debug_recording_thread(self) -> None:
        """Stop recording thread."""
        if (self.debug_recording_thread is None) or (
            self.debug_recording_queue is None
        ):
            # Not running
            return

        # NOTE: Expecting a None to have been put in self.debug_recording_queue
        # in self.end() to signal the thread to stop.

        # Wait until the thread has finished to ensure that files are fully written
        await self.hass.async_add_executor_job(self.debug_recording_thread.join)

        self.debug_recording_queue = None
        self.debug_recording_thread = None

    async def process_volume_only(
        self, audio_stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Apply volume transformation only (no VAD/audio enhancements) with optional chunking."""
        timestamp_ms = 0
        async for chunk in audio_stream:
            if self.audio_settings.volume_multiplier != 1.0:
                chunk = _multiply_volume(chunk, self.audio_settings.volume_multiplier)

            for sub_chunk in chunk_samples(
                chunk, BYTES_PER_CHUNK, self.audio_chunking_buffer
            ):
                yield EnhancedAudioChunk(
                    audio=sub_chunk,
                    timestamp_ms=timestamp_ms,
                    speech_probability=None,  # no VAD
                )
                timestamp_ms += MS_PER_CHUNK

    async def process_enhance_audio(
        self, audio_stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Split audio into chunks and apply VAD/noise suppression/auto gain/volume transformation."""
        assert self.audio_enhancer is not None

        timestamp_ms = 0
        async for dirty_samples in audio_stream:
            if self.audio_settings.volume_multiplier != 1.0:
                # Static gain
                dirty_samples = _multiply_volume(
                    dirty_samples, self.audio_settings.volume_multiplier
                )

            # Split into chunks for audio enhancements/VAD
            for dirty_chunk in chunk_samples(
                dirty_samples, BYTES_PER_CHUNK, self.audio_chunking_buffer
            ):
                yield self.audio_enhancer.enhance_chunk(dirty_chunk, timestamp_ms)
                timestamp_ms += MS_PER_CHUNK


def _multiply_volume(chunk: bytes, volume_multiplier: float) -> bytes:
    """Multiplies 16-bit PCM samples by a constant."""

    def _clamp(val: float) -> float:
        """Clamp to signed 16-bit."""
        return max(-32768, min(32767, val))

    return array.array(
        "h",
        (int(_clamp(value * volume_multiplier)) for value in array.array("h", chunk)),
    ).tobytes()


def _pipeline_debug_recording_thread_proc(
    run_recording_dir: Path,
    queue: Queue[str | bytes | None],
    message_timeout: float = 5,
) -> None:
    wav_writer: wave.Wave_write | None = None

    try:
        _LOGGER.debug("Saving wake/stt audio to %s", run_recording_dir)
        run_recording_dir.mkdir(parents=True, exist_ok=True)

        while True:
            message = queue.get(timeout=message_timeout)
            if message is None:
                # Stop signal
                break

            if isinstance(message, str):
                # New WAV file name
                if wav_writer is not None:
                    wav_writer.close()

                wav_path = run_recording_dir / f"{message}.wav"
                wav_writer = wave.open(str(wav_path), "wb")
                wav_writer.setframerate(SAMPLE_RATE)
                wav_writer.setsampwidth(SAMPLE_WIDTH)
                wav_writer.setnchannels(SAMPLE_CHANNELS)
            elif isinstance(message, bytes):
                # Chunk of 16-bit mono audio at 16Khz
                if wav_writer is not None:
                    wav_writer.writeframes(message)
    except Empty:
        pass  # occurs when pipeline has unexpected error
    except Exception:
        _LOGGER.exception("Unexpected error in debug recording thread")
    finally:
        if wav_writer is not None:
            wav_writer.close()


@dataclass(kw_only=True)
class PipelineInput:
    """Input to a pipeline run."""

    run: PipelineRun

    session: chat_session.ChatSession
    """Session for the conversation."""

    stt_metadata: stt.SpeechMetadata | None = None
    """Metadata of stt input audio. Required when start_stage = stt."""

    stt_stream: AsyncIterable[bytes] | None = None
    """Input audio for stt. Required when start_stage = stt."""

    wake_word_phrase: str | None = None
    """Optional key used to de-duplicate wake-ups for local wake word detection."""

    intent_input: str | None = None
    """Input for conversation agent. Required when start_stage = intent."""

    tts_input: str | None = None
    """Input for text-to-speech. Required when start_stage = tts."""

    conversation_extra_system_prompt: str | None = None
    """Extra prompt information for the conversation agent."""

    device_id: str | None = None
    """Identifier of the device that is processing the input/output of the pipeline."""

    async def execute(self) -> None:
        """Run pipeline."""
        self.run.start(
            conversation_id=self.session.conversation_id, device_id=self.device_id
        )
        current_stage: PipelineStage | None = self.run.start_stage
        stt_audio_buffer: list[EnhancedAudioChunk] = []
        stt_processed_stream: AsyncIterable[EnhancedAudioChunk] | None = None

        if self.stt_stream is not None:
            if self.run.audio_settings.needs_processor:
                # VAD/noise suppression/auto gain/volume
                stt_processed_stream = self.run.process_enhance_audio(self.stt_stream)
            else:
                # Volume multiplier only
                stt_processed_stream = self.run.process_volume_only(self.stt_stream)

        try:
            if current_stage == PipelineStage.WAKE_WORD:
                # wake-word-detection
                assert stt_processed_stream is not None
                detect_result = await self.run.wake_word_detection(
                    stt_processed_stream, stt_audio_buffer
                )
                if detect_result is None:
                    # No wake word. Abort the rest of the pipeline.
                    return

                current_stage = PipelineStage.STT

            # speech-to-text
            intent_input = self.intent_input
            if current_stage == PipelineStage.STT:
                assert self.stt_metadata is not None
                assert stt_processed_stream is not None

                if self.wake_word_phrase is not None:
                    # Avoid duplicate wake-ups by checking cooldown
                    last_wake_up = self.run.hass.data[DATA_LAST_WAKE_UP].get(
                        self.wake_word_phrase
                    )
                    if last_wake_up is not None:
                        sec_since_last_wake_up = time.monotonic() - last_wake_up
                        if sec_since_last_wake_up < WAKE_WORD_COOLDOWN:
                            _LOGGER.debug(
                                "Speech-to-text cancelled to avoid duplicate wake-up for %s",
                                self.wake_word_phrase,
                            )
                            raise DuplicateWakeUpDetectedError(self.wake_word_phrase)

                    # Record last wake up time to block duplicate detections
                    self.run.hass.data[DATA_LAST_WAKE_UP][self.wake_word_phrase] = (
                        time.monotonic()
                    )

                stt_input_stream = stt_processed_stream

                if stt_audio_buffer:
                    # Send audio in the buffer first to speech-to-text, then move on to stt_stream.
                    # This is basically an async itertools.chain.
                    async def buffer_then_audio_stream() -> AsyncGenerator[
                        EnhancedAudioChunk
                    ]:
                        # Buffered audio
                        for chunk in stt_audio_buffer:
                            yield chunk

                        # Streamed audio
                        assert stt_processed_stream is not None
                        async for chunk in stt_processed_stream:
                            yield chunk

                    stt_input_stream = buffer_then_audio_stream()

                intent_input = await self.run.speech_to_text(
                    self.stt_metadata,
                    stt_input_stream,
                )
                current_stage = PipelineStage.INTENT

            if self.run.end_stage != PipelineStage.STT:
                tts_input = self.tts_input

                if current_stage == PipelineStage.INTENT:
                    # intent-recognition
                    assert intent_input is not None
                    tts_input = await self.run.recognize_intent(
                        intent_input,
                        self.session.conversation_id,
                        self.device_id,
                        self.conversation_extra_system_prompt,
                    )
                    if tts_input.strip():
                        current_stage = PipelineStage.TTS
                    else:
                        # Skip TTS
                        current_stage = PipelineStage.END

                if self.run.end_stage != PipelineStage.INTENT:
                    # text-to-speech
                    if current_stage == PipelineStage.TTS:
                        assert tts_input is not None
                        await self.run.text_to_speech(tts_input)

        except PipelineError as err:
            self.run.process_event(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": err.code, "message": err.message},
                )
            )
        finally:
            # Always end the run since it needs to shut down the debug recording
            # thread, etc.
            await self.run.end()

    async def validate(self) -> None:
        """Validate pipeline input against start stage."""
        if self.run.start_stage in (PipelineStage.WAKE_WORD, PipelineStage.STT):
            if self.run.pipeline.stt_engine is None:
                raise PipelineRunValidationError(
                    "the pipeline does not support speech-to-text"
                )
            if self.stt_metadata is None:
                raise PipelineRunValidationError(
                    "stt_metadata is required for speech-to-text"
                )
            if self.stt_stream is None:
                raise PipelineRunValidationError(
                    "stt_stream is required for speech-to-text"
                )
        elif self.run.start_stage == PipelineStage.INTENT:
            if self.intent_input is None:
                raise PipelineRunValidationError(
                    "intent_input is required for intent recognition"
                )
        elif self.run.start_stage == PipelineStage.TTS:
            if self.tts_input is None:
                raise PipelineRunValidationError(
                    "tts_input is required for text-to-speech"
                )
        if self.run.end_stage == PipelineStage.TTS:
            if self.run.pipeline.tts_engine is None:
                raise PipelineRunValidationError(
                    "the pipeline does not support text-to-speech"
                )

        start_stage_index = PIPELINE_STAGE_ORDER.index(self.run.start_stage)
        end_stage_index = PIPELINE_STAGE_ORDER.index(self.run.end_stage)

        prepare_tasks = []

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.WAKE_WORD)
            <= end_stage_index
        ):
            prepare_tasks.append(self.run.prepare_wake_word_detection())

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.STT)
            <= end_stage_index
        ):
            # self.stt_metadata can't be None or we'd raise above
            prepare_tasks.append(self.run.prepare_speech_to_text(self.stt_metadata))  # type: ignore[arg-type]

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.INTENT)
            <= end_stage_index
        ):
            prepare_tasks.append(self.run.prepare_recognize_intent(self.session))

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.TTS)
            <= end_stage_index
        ):
            prepare_tasks.append(self.run.prepare_text_to_speech())

        if prepare_tasks:
            await asyncio.gather(*prepare_tasks)


class PipelinePreferred(CollectionError):
    """Raised when attempting to delete the preferred pipelen."""

    def __init__(self, item_id: str) -> None:
        """Initialize pipeline preferred error."""
        super().__init__(f"Item {item_id} preferred.")
        self.item_id = item_id


class SerializedPipelineStorageCollection(SerializedStorageCollection):
    """Serialized pipeline storage collection."""

    preferred_item: str


class PipelineStorageCollection(
    StorageCollection[Pipeline, SerializedPipelineStorageCollection]
):
    """Pipeline storage collection."""

    _preferred_item: str

    async def _async_load_data(self) -> SerializedPipelineStorageCollection | None:
        """Load the data."""
        if not (data := await super()._async_load_data()):
            pipeline = await _async_create_default_pipeline(self.hass, self)
            self._preferred_item = pipeline.id
            return data

        self._preferred_item = data["preferred_item"]

        return data

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        validated_data: dict = validate_language(data)
        return validated_data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return ulid_util.ulid_now()

    async def _update_data(self, item: Pipeline, update_data: dict) -> Pipeline:
        """Return a new updated item."""
        update_data = validate_language(update_data)
        return Pipeline(id=item.id, **update_data)

    def _create_item(self, item_id: str, data: dict) -> Pipeline:
        """Create an item from validated config."""
        return Pipeline(id=item_id, **data)

    def _deserialize_item(self, data: dict) -> Pipeline:
        """Create an item from its serialized representation."""
        return Pipeline.from_json(data)

    def _serialize_item(self, item_id: str, item: Pipeline) -> dict:
        """Return the serialized representation of an item for storing."""
        return item.to_json()

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if self._preferred_item == item_id:
            raise PipelinePreferred(item_id)
        await super().async_delete_item(item_id)

    @callback
    def async_get_preferred_item(self) -> str:
        """Get the id of the preferred item."""
        return self._preferred_item

    @callback
    def async_set_preferred_item(self, item_id: str) -> None:
        """Set the preferred pipeline."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)
        self._preferred_item = item_id
        self._async_schedule_save()

    @callback
    def _data_to_save(self) -> SerializedPipelineStorageCollection:
        """Return JSON-compatible date for storing to file."""
        base_data = super()._base_data_to_save()
        return {
            "items": base_data["items"],
            "preferred_item": self._preferred_item,
        }


class PipelineStorageCollectionWebsocket(
    StorageCollectionWebsocket[PipelineStorageCollection]
):
    """Class to expose storage collection management over websocket."""

    @callback
    def async_setup(self, hass: HomeAssistant) -> None:
        """Set up the websocket commands."""
        super().async_setup(hass)

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/get",
            self.ws_get_item,
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    vol.Required("type"): f"{self.api_prefix}/get",
                    vol.Optional(self.item_id_key): str,
                }
            ),
        )

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/set_preferred",
            websocket_api.require_admin(
                websocket_api.async_response(self.ws_set_preferred_item)
            ),
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    vol.Required("type"): f"{self.api_prefix}/set_preferred",
                    vol.Required(self.item_id_key): str,
                }
            ),
        )

    async def ws_delete_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Delete an item."""
        try:
            await super().ws_delete_item(hass, connection, msg)
        except PipelinePreferred as exc:
            connection.send_error(msg["id"], websocket_api.ERR_NOT_ALLOWED, str(exc))

    @callback
    def ws_get_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Get an item."""
        item_id = msg.get(self.item_id_key)
        if item_id is None:
            item_id = self.storage_collection.async_get_preferred_item()

        if item_id.startswith("conversation.") and hass.states.get(item_id):
            connection.send_result(
                msg["id"], _async_get_pipeline_from_conversation_entity(hass, item_id)
            )
            return

        if item_id not in self.storage_collection.data:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {item_id}",
            )
            return

        connection.send_result(msg["id"], self.storage_collection.data[item_id])

    @callback
    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items."""
        connection.send_result(
            msg["id"],
            {
                "pipelines": async_get_pipelines(hass),
                "preferred_pipeline": self.storage_collection.async_get_preferred_item(),
            },
        )

    async def ws_set_preferred_item(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Set the preferred item."""
        try:
            self.storage_collection.async_set_preferred_item(msg[self.item_id_key])
        except ItemNotFound:
            connection.send_error(
                msg["id"], websocket_api.ERR_NOT_FOUND, "unknown item"
            )
            return
        connection.send_result(msg["id"])


class PipelineRuns:
    """Class managing pipelineruns."""

    def __init__(self, pipeline_store: PipelineStorageCollection) -> None:
        """Initialize."""
        self._pipeline_runs: dict[str, dict[str, PipelineRun]] = defaultdict(dict)
        self._pipeline_store = pipeline_store
        pipeline_store.async_add_listener(self._change_listener)

    def add_run(self, pipeline_run: PipelineRun) -> None:
        """Add pipeline run."""
        pipeline_id = pipeline_run.pipeline.id
        self._pipeline_runs[pipeline_id][pipeline_run.id] = pipeline_run

    def remove_run(self, pipeline_run: PipelineRun) -> None:
        """Remove pipeline run."""
        pipeline_id = pipeline_run.pipeline.id
        self._pipeline_runs[pipeline_id].pop(pipeline_run.id)

    async def _change_listener(
        self, change_type: str, item_id: str, change: dict
    ) -> None:
        """Handle pipeline store changes."""
        if change_type != CHANGE_UPDATED:
            return
        if pipeline_runs := self._pipeline_runs.get(item_id):
            # Create a temporary list in case the list is modified while we iterate
            for pipeline_run in list(pipeline_runs.values()):
                pipeline_run.abort_wake_word_detection = True


@dataclass(slots=True)
class DeviceAudioQueue:
    """Audio capture queue for a satellite device."""

    queue: asyncio.Queue[bytes | None]
    """Queue of audio chunks (None = stop signal)"""

    id: str = field(default_factory=ulid_util.ulid_now)
    """Unique id to ensure the correct audio queue is cleaned up in websocket API."""

    overflow: bool = False
    """Flag to be set if audio samples were dropped because the queue was full."""


@dataclass(slots=True)
class AssistDevice:
    """Assist device."""

    domain: str
    unique_id_prefix: str


class PipelineData:
    """Store and debug data stored in hass.data."""

    def __init__(self, pipeline_store: PipelineStorageCollection) -> None:
        """Initialize."""
        self.pipeline_store = pipeline_store
        self.pipeline_debug: dict[str, LimitedSizeDict[str, PipelineRunDebug]] = {}
        self.pipeline_devices: dict[str, AssistDevice] = {}
        self.pipeline_runs = PipelineRuns(pipeline_store)
        self.device_audio_queues: dict[str, DeviceAudioQueue] = {}


@dataclass(slots=True)
class PipelineRunDebug:
    """Debug data for a pipelinerun."""

    events: list[PipelineEvent] = field(default_factory=list, init=False)
    timestamp: str = field(
        default_factory=lambda: dt_util.utcnow().isoformat(),
        init=False,
    )


class PipelineStore(Store[SerializedPipelineStorageCollection]):
    """Store pipeline data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: SerializedPipelineStorageCollection,
    ) -> SerializedPipelineStorageCollection:
        """Migrate to the new version."""
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 adds wake word configuration
            for pipeline in old_data["items"]:
                # Populate keys which were introduced before version 1.2
                pipeline.setdefault("wake_word_entity", None)
                pipeline.setdefault("wake_word_id", None)

        if old_major_version > 1:
            raise NotImplementedError
        return old_data


@singleton(KEY_ASSIST_PIPELINE, async_=True)
async def async_setup_pipeline_store(hass: HomeAssistant) -> PipelineData:
    """Set up the pipeline storage collection."""
    pipeline_store = PipelineStorageCollection(
        PipelineStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )
    )
    await pipeline_store.async_load()
    PipelineStorageCollectionWebsocket(
        pipeline_store,
        f"{DOMAIN}/pipeline",
        "pipeline",
        PIPELINE_FIELDS,
        PIPELINE_FIELDS,
    ).async_setup(hass)
    return PipelineData(pipeline_store)


@callback
def async_migrate_engine(
    hass: HomeAssistant,
    engine_type: Literal["conversation", "stt", "tts", "wake_word"],
    old_value: str,
    new_value: str,
) -> None:
    """Register a migration of an engine used in pipelines."""
    hass.data.setdefault(DATA_MIGRATIONS, {})[engine_type] = (old_value, new_value)

    # Run migrations when config is already loaded
    if DATA_CONFIG in hass.data:
        hass.async_create_background_task(
            async_run_migrations(hass), "assist_pipeline_migration", eager_start=True
        )


async def async_run_migrations(hass: HomeAssistant) -> None:
    """Run pipeline migrations."""
    if not (migrations := hass.data.get(DATA_MIGRATIONS)):
        return

    engine_attr = {
        "conversation": "conversation_engine",
        "stt": "stt_engine",
        "tts": "tts_engine",
        "wake_word": "wake_word_entity",
    }

    updates = []

    for pipeline in async_get_pipelines(hass):
        attr_updates = {}
        for engine_type, (old_value, new_value) in migrations.items():
            if getattr(pipeline, engine_attr[engine_type]) == old_value:
                attr_updates[engine_attr[engine_type]] = new_value

        if attr_updates:
            updates.append((pipeline, attr_updates))

    for pipeline, attr_updates in updates:
        await async_update_pipeline(hass, pipeline, **attr_updates)


@dataclass
class PipelineConversationData:
    """Hold data for the duration of a conversation."""

    continue_conversation_agent: str | None = None
    """The agent that requested the conversation to be continued."""


@callback
def async_get_pipeline_conversation_data(
    hass: HomeAssistant, session: chat_session.ChatSession
) -> PipelineConversationData:
    """Get the pipeline data for a specific conversation."""
    all_conversation_data = hass.data.get(KEY_PIPELINE_CONVERSATION_DATA)
    if all_conversation_data is None:
        all_conversation_data = {}
        hass.data[KEY_PIPELINE_CONVERSATION_DATA] = all_conversation_data

    data = all_conversation_data.get(session.conversation_id)

    if data is not None:
        return data

    @callback
    def do_cleanup() -> None:
        """Handle cleanup."""
        all_conversation_data.pop(session.conversation_id)

    session.async_on_cleanup(do_cleanup)

    data = all_conversation_data[session.conversation_id] = PipelineConversationData()
    return data
