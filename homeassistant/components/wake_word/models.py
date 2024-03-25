"""Wake word models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WakeWord:
    """Wake word model."""

    id: str
    """Id of wake word model"""

    name: str
    """Name of wake word model"""

    phrase: str | None = None
    """Wake word phrase used to trigger model"""


@dataclass
class DetectionResult:
    """Result of wake word detection."""

    wake_word_id: str
    """Id of detected wake word"""

    wake_word_phrase: str
    """Normalized phrase for the detected wake word"""

    timestamp: int | None
    """Timestamp of audio chunk with detected wake word"""

    queued_audio: list[tuple[bytes, int]] | None = None
    """Audio chunks that were queued when wake word was detected."""
