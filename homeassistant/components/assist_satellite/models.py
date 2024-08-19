"""Models for assist satellite."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class SatelliteConfig:
    """Configuration of satellite."""

    default_pipeline: str | None = None
    """Pipeline id to use by default (None = preferred)."""

    finished_speaking_seconds: float = 1.0
    """Seconds of silence before voice command is finished."""


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

    WAITING_FOR_INPUT = "waiting_for_input"
    """Device is waiting for user input, such as a wake word."""

    LISTENING_WAKE_WORD = "listening_wake_word"
    """Device is streaming audio for wake word detection to Home Assistant."""

    LISTENING_COMMAND = "listening_command"
    """Device is streaming audio with the voice command to Home Assistant."""

    PROCESSING = "processing"
    """Device has stopped streaming audio and is waiting for Home Assistant to
    process the voice command."""

    RESPONDING = "responding"
    """Device is speaking the response."""
