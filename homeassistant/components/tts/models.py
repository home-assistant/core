"""Text-to-speech data models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    """A TTS voice."""

    voice_id: str
    name: str
