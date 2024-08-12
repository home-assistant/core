"""Models for assist satellite."""

from dataclasses import dataclass
from enum import IntFlag, StrEnum


@dataclass
class SatelliteConfig:
    """Configuration of satellite."""

    default_pipeline: str | None = None
    """Pipeline id to use by default (None = preferred)."""

    finished_speaking_seconds: float = 1.0
    """Seconds of silence before voice command is finished."""


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of the satellite entity."""

    AUDIO_INPUT = 1
    """Satellite is capable of recording and streaming audio to Home Assistant."""

    AUDIO_OUTPUT = 2
    """Satellite is capable of playing audio."""


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

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
