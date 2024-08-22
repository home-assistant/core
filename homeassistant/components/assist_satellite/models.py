"""Models for assist satellite."""

from dataclasses import dataclass
from enum import IntFlag, StrEnum


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

    LISTENING_WAKE_WORD = "listening_wake_word"
    """Device is streaming audio for wake word detection to Home Assistant."""

    LISTENING_COMMAND = "listening_command"
    """Device is streaming audio with the voice command to Home Assistant."""

    PROCESSING = "processing"
    """Home Assistant is processing the voice command."""

    RESPONDING = "responding"
    """Device is speaking the response."""


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of Assist satellite entity."""

    TRIGGER_PIPELINE = 1
    """Device supports remote triggering of a pipeline."""


@dataclass(frozen=True)
class PipelineRunConfig:
    """Configuration for a satellite pipeline run."""

    wake_word_names: list[str] | None = None
    """Wake word names to listen for (start_stage = wake)."""

    announce_text: str | None = None
    """Text to announce using text-to-speech (start_stage = wake, stt, or tts)."""


@dataclass(frozen=True)
class PipelineRunResult:
    """Result of a pipeline run."""

    detected_wake_word: str | None = None
    """Name of detected wake word (None if timeout)."""

    command_text: str | None = None
    """Transcript of speech-to-text for voice command."""
