"""Wake word models."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WakeWord:
    """Wake word model."""

    id: str
    name: str


@dataclass
class DetectionResult:
    """Result of wake word detection."""

    wake_word_id: str
    """Id of detected wake word"""

    timestamp: int | None
    """Timestamp of audio chunk with detected wake word"""

    queued_audio: list[tuple[bytes, int]] | None = None
    """Audio chunks that were queued when wake word was detected."""
