"""Models for assist satellite."""

from dataclasses import dataclass
from enum import IntFlag, StrEnum, auto

from homeassistant.const import STATE_UNAVAILABLE


@dataclass
class SatelliteCapabilities:
    """Capabilities of satellite."""

    wake_words: list[str]
    """Available on-device wake words."""

    max_active_wake_words: int | None = None
    """Maximum number of active wake words."""


@dataclass
class SatelliteConfig:
    """Configuration of satellite."""

    active_wake_words: list[str]
    """List of wake words that should be active (empty = streaming)."""

    finished_speaking_seconds: float | None = None
    """Seconds of silence before voice command is finished (on-device VAD only)."""


@dataclass
class PipelineRunConfig:
    """Configuration for a satellite pipeline run."""

    wake_word_names: list[str] | None = None
    """Wake word names to listen for (start_stage = wake)."""

    announce_text: str | None = None
    """Text to announce using text-to-speech (start_stage = tts)."""


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
