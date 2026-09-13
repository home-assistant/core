"""Dependency-neutral models for Assist pipelines."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from homeassistant.util import dt as dt_util, ulid as ulid_util


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
        """Create an instance from a JSON serialization."""
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
