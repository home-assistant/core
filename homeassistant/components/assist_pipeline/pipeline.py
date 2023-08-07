"""Classes for voice assistant pipelines."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Iterable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import (
    conversation,
    media_source,
    stt,
    tts,
    wake_word,
    websocket_api,
)
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.collection import (
    CollectionError,
    ItemNotFound,
    SerializedStorageCollection,
    StorageCollection,
    StorageCollectionWebsocket,
)
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util import (
    dt as dt_util,
    language as language_util,
    ulid as ulid_util,
)
from homeassistant.util.limited_size_dict import LimitedSizeDict

from .const import DOMAIN
from .error import (
    IntentRecognitionError,
    PipelineError,
    PipelineNotFound,
    SpeechToTextError,
    TextToSpeechError,
    WakeWordDetectionError,
    WakeWordTimeoutError,
)
from .vad import VoiceActivityTimeout, VoiceCommandSegmenter

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.pipelines"
STORAGE_VERSION = 1

ENGINE_LANGUAGE_PAIRS = (
    ("stt_engine", "stt_language"),
    ("tts_engine", "tts_language"),
)


def validate_language(data: dict[str, Any]) -> Any:
    """Validate language settings."""
    for engine, language in ENGINE_LANGUAGE_PAIRS:
        if data[engine] is not None and data[language] is None:
            raise vol.Invalid(f"Need language {language} for {engine} {data[engine]}")
    return data


PIPELINE_FIELDS = {
    vol.Required("conversation_engine"): str,
    vol.Required("conversation_language"): str,
    vol.Required("language"): str,
    vol.Required("name"): str,
    vol.Required("stt_engine"): vol.Any(str, None),
    vol.Required("stt_language"): vol.Any(str, None),
    vol.Required("tts_engine"): vol.Any(str, None),
    vol.Required("tts_language"): vol.Any(str, None),
    vol.Required("tts_voice"): vol.Any(str, None),
}

STORED_PIPELINE_RUNS = 10

SAVE_DELAY = 10


async def _async_resolve_default_pipeline_settings(
    hass: HomeAssistant,
    stt_engine_id: str | None,
    tts_engine_id: str | None,
) -> dict[str, str | None]:
    """Resolve settings for a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines if none are specified.
    """
    conversation_language = "en"
    pipeline_language = "en"
    pipeline_name = "Home Assistant"
    stt_engine = None
    stt_language = None
    tts_engine = None
    tts_language = None
    tts_voice = None

    # Find a matching language supported by the Home Assistant conversation agent
    conversation_languages = language_util.matches(
        hass.config.language,
        await conversation.async_get_conversation_languages(
            hass, conversation.HOME_ASSISTANT_AGENT
        ),
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

    if stt_engine_id == "cloud" and tts_engine_id == "cloud":
        pipeline_name = "Home Assistant Cloud"

    return {
        "conversation_engine": conversation.HOME_ASSISTANT_AGENT,
        "conversation_language": conversation_language,
        "language": hass.config.language,
        "name": pipeline_name,
        "stt_engine": stt_engine_id,
        "stt_language": stt_language,
        "tts_engine": tts_engine_id,
        "tts_language": tts_language,
        "tts_voice": tts_voice,
    }


async def _async_create_default_pipeline(
    hass: HomeAssistant, pipeline_store: PipelineStorageCollection
) -> Pipeline:
    """Create a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines.
    """
    pipeline_settings = await _async_resolve_default_pipeline_settings(hass, None, None)
    return await pipeline_store.async_create_item(pipeline_settings)


async def async_create_default_pipeline(
    hass: HomeAssistant, stt_engine_id: str, tts_engine_id: str
) -> Pipeline | None:
    """Create a pipeline with default settings.

    The default pipeline will use the homeassistant conversation agent and the
    specified stt / tts engines.
    """
    pipeline_data: PipelineData = hass.data[DOMAIN]
    pipeline_store = pipeline_data.pipeline_store
    pipeline_settings = await _async_resolve_default_pipeline_settings(
        hass, stt_engine_id, tts_engine_id
    )
    if (
        pipeline_settings["stt_engine"] != stt_engine_id
        or pipeline_settings["tts_engine"] != tts_engine_id
    ):
        return None
    return await pipeline_store.async_create_item(pipeline_settings)


@callback
def async_get_pipeline(hass: HomeAssistant, pipeline_id: str | None = None) -> Pipeline:
    """Get a pipeline by id or the preferred pipeline."""
    pipeline_data: PipelineData = hass.data[DOMAIN]

    if pipeline_id is None:
        # A pipeline was not specified, use the preferred one
        pipeline_id = pipeline_data.pipeline_store.async_get_preferred_item()

    pipeline = pipeline_data.pipeline_store.data.get(pipeline_id)

    # If invalid pipeline ID was specified
    if pipeline is None:
        raise PipelineNotFound(
            "pipeline_not_found", f"Pipeline {pipeline_id} not found"
        )

    return pipeline


@callback
def async_get_pipelines(hass: HomeAssistant) -> Iterable[Pipeline]:
    """Get all pipelines."""
    pipeline_data: PipelineData = hass.data[DOMAIN]

    return pipeline_data.pipeline_store.data.values()


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_END = "run-end"
    WAKE_WORD_START = "wake_word-start"
    WAKE_WORD_END = "wake_word-end"
    STT_START = "stt-start"
    STT_END = "stt-end"
    INTENT_START = "intent-start"
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


PipelineEventCallback = Callable[[PipelineEvent], None]


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

    id: str = field(default_factory=ulid_util.ulid)

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
        }


class PipelineStage(StrEnum):
    """Stages of a pipeline."""

    WAKE_WORD = "wake_word"
    STT = "stt"
    INTENT = "intent"
    TTS = "tts"


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
    tts_audio_output: str | None = None
    wake_word_settings: WakeWordSettings | None = None

    id: str = field(default_factory=ulid_util.ulid)
    stt_provider: stt.SpeechToTextEntity | stt.Provider = field(init=False)
    tts_engine: str = field(init=False)
    tts_options: dict | None = field(init=False, default=None)
    wake_word_engine: str = field(init=False)
    wake_word_provider: wake_word.WakeWordDetectionEntity = field(init=False)

    def __post_init__(self) -> None:
        """Set language for pipeline."""
        self.language = self.pipeline.language or self.hass.config.language

        # wake -> stt -> intent -> tts
        if PIPELINE_STAGE_ORDER.index(self.end_stage) < PIPELINE_STAGE_ORDER.index(
            self.start_stage
        ):
            raise InvalidPipelineStagesError(self.start_stage, self.end_stage)

        pipeline_data: PipelineData = self.hass.data[DOMAIN]
        if self.pipeline.id not in pipeline_data.pipeline_runs:
            pipeline_data.pipeline_runs[self.pipeline.id] = LimitedSizeDict(
                size_limit=STORED_PIPELINE_RUNS
            )
        pipeline_data.pipeline_runs[self.pipeline.id][self.id] = PipelineRunDebug()

    @callback
    def process_event(self, event: PipelineEvent) -> None:
        """Log an event and call listener."""
        self.event_callback(event)
        pipeline_data: PipelineData = self.hass.data[DOMAIN]
        if self.id not in pipeline_data.pipeline_runs[self.pipeline.id]:
            # This run has been evicted from the logged pipeline runs already
            return
        pipeline_data.pipeline_runs[self.pipeline.id][self.id].events.append(event)

    def start(self) -> None:
        """Emit run start event."""
        data = {
            "pipeline": self.pipeline.id,
            "language": self.language,
        }
        if self.runner_data is not None:
            data["runner_data"] = self.runner_data

        self.process_event(PipelineEvent(PipelineEventType.RUN_START, data))

    def end(self) -> None:
        """Emit run end event."""
        self.process_event(
            PipelineEvent(
                PipelineEventType.RUN_END,
            )
        )

    async def prepare_wake_word_detection(self) -> None:
        """Prepare wake-word-detection."""
        # Need to add to pipeline store
        engine = wake_word.async_default_engine(self.hass)
        if engine is None:
            raise WakeWordDetectionError(
                code="wake-engine-missing",
                message="No wake word engine",
            )

        wake_word_provider = wake_word.async_get_wake_word_detection_entity(
            self.hass, engine
        )
        if wake_word_provider is None:
            raise WakeWordDetectionError(
                code="wake-provider-missing",
                message=f"No wake-word-detection provider for: {engine}",
            )

        self.wake_word_engine = engine
        self.wake_word_provider = wake_word_provider

    async def wake_word_detection(
        self,
        stream: AsyncIterable[bytes],
        audio_buffer: list[bytes],
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

        # Remove language since it doesn't apply to wake words yet
        metadata_dict.pop("language", None)

        self.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_START,
                {
                    "engine": self.wake_word_engine,
                    "metadata": metadata_dict,
                },
            )
        )

        wake_word_settings = self.wake_word_settings or WakeWordSettings()

        wake_word_vad: VoiceActivityTimeout | None = None
        if (wake_word_settings.timeout is not None) and (
            wake_word_settings.timeout > 0
        ):
            # Use VAD to determine timeout
            wake_word_vad = VoiceActivityTimeout(wake_word_settings.timeout)

        # Audio chunk buffer.
        audio_bytes_to_buffer = int(
            wake_word_settings.audio_seconds_to_buffer * 16000 * 2
        )
        audio_ring_buffer = b""

        async def timestamped_stream() -> AsyncIterable[tuple[bytes, int]]:
            """Yield audio with timestamps (milliseconds since start of stream)."""
            nonlocal audio_ring_buffer

            timestamp_ms = 0
            async for chunk in stream:
                yield chunk, timestamp_ms
                timestamp_ms += (len(chunk) // 2) // 16  # milliseconds @ 16Khz

                # Keeping audio right before wake word detection allows the
                # voice command to be spoken immediately after the wake word.
                if audio_bytes_to_buffer > 0:
                    audio_ring_buffer += chunk
                    if len(audio_ring_buffer) > audio_bytes_to_buffer:
                        # A proper ring buffer would be far more efficient
                        audio_ring_buffer = audio_ring_buffer[
                            len(audio_ring_buffer) - audio_bytes_to_buffer :
                        ]

                if (wake_word_vad is not None) and (not wake_word_vad.process(chunk)):
                    raise WakeWordTimeoutError(
                        code="wake-word-timeout", message="Wake word was not detected"
                    )

        try:
            # Detect wake word(s)
            result = await self.wake_word_provider.async_process_audio_stream(
                timestamped_stream()
            )

            if audio_ring_buffer:
                # All audio kept from right before the wake word was detected as
                # a single chunk.
                audio_buffer.append(audio_ring_buffer)
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
            if result.queued_audio:
                # Add audio that was pending at detection
                for chunk_ts in result.queued_audio:
                    audio_buffer.append(chunk_ts[0])

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
        stream: AsyncIterable[bytes],
    ) -> str:
        """Run speech-to-text portion of pipeline. Returns the spoken text."""
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

        try:
            segmenter = VoiceCommandSegmenter()

            async def segment_stream(
                stream: AsyncIterable[bytes],
            ) -> AsyncGenerator[bytes, None]:
                """Stop stream when voice command is finished."""
                async for chunk in stream:
                    if not segmenter.process(chunk):
                        break

                    yield chunk

            # Transcribe audio stream
            result = await self.stt_provider.async_process_audio_stream(
                metadata, segment_stream(stream)
            )
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

    async def prepare_recognize_intent(self) -> None:
        """Prepare recognizing an intent."""
        agent_info = conversation.async_get_agent_info(
            self.hass,
            # If no conversation engine is set, use the Home Assistant agent
            # (the conversation integration default is currently the last one set)
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
        self, intent_input: str, conversation_id: str | None, device_id: str | None
    ) -> str:
        """Run intent recognition portion of pipeline. Returns text to speak."""
        if self.intent_agent is None:
            raise RuntimeError("Recognize intent was not prepared")

        self.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.intent_agent,
                    "language": self.pipeline.conversation_language,
                    "intent_input": intent_input,
                    "conversation_id": conversation_id,
                    "device_id": device_id,
                },
            )
        )

        try:
            conversation_result = await conversation.async_converse(
                hass=self.hass,
                text=intent_input,
                conversation_id=conversation_id,
                device_id=device_id,
                context=self.context,
                language=self.pipeline.conversation_language,
                agent_id=self.intent_agent,
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
                {"intent_output": conversation_result.as_dict()},
            )
        )

        speech: str = conversation_result.response.speech.get("plain", {}).get(
            "speech", ""
        )

        return speech

    async def prepare_text_to_speech(self) -> None:
        """Prepare text-to-speech."""
        # pipeline.tts_engine can't be None or this function is not called
        engine = cast(str, self.pipeline.tts_engine)

        tts_options = {}
        if self.pipeline.tts_voice is not None:
            tts_options[tts.ATTR_VOICE] = self.pipeline.tts_voice

        if self.tts_audio_output is not None:
            tts_options[tts.ATTR_AUDIO_OUTPUT] = self.tts_audio_output

        try:
            options_supported = await tts.async_support_options(
                self.hass,
                engine,
                self.pipeline.tts_language,
                tts_options,
            )
        except HomeAssistantError as err:
            raise TextToSpeechError(
                code="tts-not-supported",
                message=f"Text-to-speech engine '{engine}' not found",
            ) from err
        if not options_supported:
            raise TextToSpeechError(
                code="tts-not-supported",
                message=(
                    f"Text-to-speech engine {engine} "
                    f"does not support language {self.pipeline.tts_language} or options {tts_options}"
                ),
            )

        self.tts_engine = engine
        self.tts_options = tts_options

    async def text_to_speech(self, tts_input: str) -> str:
        """Run text-to-speech portion of pipeline. Returns URL of TTS audio."""
        self.process_event(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.tts_engine,
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
                engine=self.tts_engine,
                language=self.pipeline.tts_language,
                options=self.tts_options,
            )
            tts_media = await media_source.async_resolve_media(
                self.hass,
                tts_media_id,
                None,
            )
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during text-to-speech")
            raise TextToSpeechError(
                code="tts-failed",
                message="Unexpected error during text-to-speech",
            ) from src_error

        _LOGGER.debug("TTS result %s", tts_media)

        self.process_event(
            PipelineEvent(
                PipelineEventType.TTS_END,
                {
                    "tts_output": {
                        "media_id": tts_media_id,
                        **asdict(tts_media),
                    }
                },
            )
        )

        return tts_media.url


@dataclass
class PipelineInput:
    """Input to a pipeline run."""

    run: PipelineRun

    stt_metadata: stt.SpeechMetadata | None = None
    """Metadata of stt input audio. Required when start_stage = stt."""

    stt_stream: AsyncIterable[bytes] | None = None
    """Input audio for stt. Required when start_stage = stt."""

    intent_input: str | None = None
    """Input for conversation agent. Required when start_stage = intent."""

    tts_input: str | None = None
    """Input for text-to-speech. Required when start_stage = tts."""

    conversation_id: str | None = None

    device_id: str | None = None

    async def execute(self) -> None:
        """Run pipeline."""
        self.run.start()
        current_stage: PipelineStage | None = self.run.start_stage
        audio_buffer: list[bytes] = []

        try:
            if current_stage == PipelineStage.WAKE_WORD:
                assert self.stt_stream is not None
                detect_result = await self.run.wake_word_detection(
                    self.stt_stream, audio_buffer
                )
                if detect_result is None:
                    # No wake word. Abort the rest of the pipeline.
                    self.run.end()
                    return

                current_stage = PipelineStage.STT

            # speech-to-text
            intent_input = self.intent_input
            if current_stage == PipelineStage.STT:
                assert self.stt_metadata is not None
                assert self.stt_stream is not None

                if audio_buffer:

                    async def buffered_stream() -> AsyncGenerator[bytes, None]:
                        for chunk in audio_buffer:
                            yield chunk

                        assert self.stt_stream is not None
                        async for chunk in self.stt_stream:
                            yield chunk

                    stt_stream = cast(AsyncIterable[bytes], buffered_stream())
                else:
                    stt_stream = self.stt_stream

                intent_input = await self.run.speech_to_text(
                    self.stt_metadata,
                    stt_stream,
                )
                current_stage = PipelineStage.INTENT

            if self.run.end_stage != PipelineStage.STT:
                tts_input = self.tts_input

                if current_stage == PipelineStage.INTENT:
                    assert intent_input is not None
                    tts_input = await self.run.recognize_intent(
                        intent_input,
                        self.conversation_id,
                        self.device_id,
                    )
                    current_stage = PipelineStage.TTS

                if self.run.end_stage != PipelineStage.INTENT:
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
            return

        self.run.end()

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
            prepare_tasks.append(self.run.prepare_recognize_intent())

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
        return ulid_util.ulid()

    async def _update_data(self, item: Pipeline, update_data: dict) -> Pipeline:
        """Return a new updated item."""
        update_data = validate_language(update_data)
        return Pipeline(id=item.id, **update_data)

    def _create_item(self, item_id: str, data: dict) -> Pipeline:
        """Create an item from validated config."""
        return Pipeline(id=item_id, **data)

    def _deserialize_item(self, data: dict) -> Pipeline:
        """Create an item from its serialized representation."""
        return Pipeline(**data)

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
    def async_setup(
        self,
        hass: HomeAssistant,
        *,
        create_list: bool = True,
        create_create: bool = True,
    ) -> None:
        """Set up the websocket commands."""
        super().async_setup(hass, create_list=create_list, create_create=create_create)

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
            connection.send_error(
                msg["id"], websocket_api.const.ERR_NOT_ALLOWED, str(exc)
            )

    @callback
    def ws_get_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Get an item."""
        item_id = msg.get(self.item_id_key)
        if item_id is None:
            item_id = self.storage_collection.async_get_preferred_item()

        if item_id not in self.storage_collection.data:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_NOT_FOUND,
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
                "pipelines": self.storage_collection.async_items(),
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
                msg["id"], websocket_api.const.ERR_NOT_FOUND, "unknown item"
            )
            return
        connection.send_result(msg["id"])


@dataclass
class PipelineData:
    """Store and debug data stored in hass.data."""

    pipeline_runs: dict[str, LimitedSizeDict[str, PipelineRunDebug]]
    pipeline_store: PipelineStorageCollection
    pipeline_devices: set[str] = field(default_factory=set, init=False)


@dataclass
class PipelineRunDebug:
    """Debug data for a pipelinerun."""

    events: list[PipelineEvent] = field(default_factory=list, init=False)
    timestamp: str = field(
        default_factory=lambda: dt_util.utcnow().isoformat(),
        init=False,
    )


@singleton(DOMAIN)
async def async_setup_pipeline_store(hass: HomeAssistant) -> PipelineData:
    """Set up the pipeline storage collection."""
    pipeline_store = PipelineStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY)
    )
    await pipeline_store.async_load()
    PipelineStorageCollectionWebsocket(
        pipeline_store,
        f"{DOMAIN}/pipeline",
        "pipeline",
        PIPELINE_FIELDS,
        PIPELINE_FIELDS,
    ).async_setup(hass)
    return PipelineData({}, pipeline_store)
