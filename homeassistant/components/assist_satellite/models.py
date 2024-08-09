"""Models for assist satellite."""

from dataclasses import dataclass, field
from enum import IntFlag, StrEnum, auto

from homeassistant.const import STATE_UNAVAILABLE


@dataclass
class SatelliteCapabilities:
    """Capabilities of satellite."""

    wake_words: list[str]
    """Available wake words."""

    max_active_wake_words: int | None = None
    """Maximum number of active wake words."""


@dataclass
class SatelliteConfig:
    """Configuration of satellite."""

    active_wake_words: list[str]
    """List of wake words that are actively being listened for."""

    wake_word_entity_id: str | None = None
    """Entity id of streaming wake word provider (None = on-device)."""

    default_pipeline: str | None = None
    """Pipeline id to use by default (None = preferred)."""

    wake_word_pipeline: dict[str, str] = field(default_factory=dict)
    """Mapping between wake words and pipeline ids.

    If a wake word is not present, then use default_pipeline_id.
    """

    finished_speaking_seconds: float = 1.0
    """Seconds of silence before voice command is finished."""


@dataclass
class PipelineRunConfig:
    """Configuration for a satellite pipeline run."""

    wake_word_names: list[str] | None = None
    """Wake word names to listen for (start_stage = wake)."""

    announce_text: str | None = None
    """Text to announce using text-to-speech (start_stage = wake, stt, or tts)."""


@dataclass
class PipelineRunResult:
    """Result of a pipeline run."""

    detected_wake_word: str | None = None
    """Name of detected wake word (None if timeout)."""

    command_text: str | None = None
    """Transcript of speech-to-text for voice command."""


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of the satellite entity."""

    AUDIO_INPUT = auto()
    """Satellite is capable of recording and streaming audio to Home Assistant."""

    AUDIO_OUTPUT = auto()
    """Satellite is capable of playing audio."""

    VOICE_ACTIVITY_DETECTION = auto()
    """Satellite is capable of on-device VAD."""

    WAKE_WORD = auto()
    """Satellite is capable of on-device wake word detection."""

    TRIGGER = auto()
    """Satellite supports remotely triggering pipelines."""


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

    UNAVAILABLE = STATE_UNAVAILABLE
    """Satellite is not connected."""

    IDLE = "idle"
    """Device is waiting for the wake word."""

    LISTENING = "listening"
    """Device is streaming audio with the command to Home Assistant."""

    PROCESSING = "processing"
    """Device has stopped streaming audio and is waiting for Home Assistant to
    process the voice command."""

    RESPONDING = "responding"
    """Device is speaking the response."""

    MUTED = "muted"
    """Device is muted (in software or hardware)."""
