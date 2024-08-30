"""Models for assist satellite."""

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

    ANNOUNCE = 1
    """Device supports remotely triggered announcements."""
