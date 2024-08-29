"""Models for assist satellite."""

from dataclasses import dataclass
from enum import IntFlag, StrEnum

from homeassistant.components.assist_pipeline import PipelineStage


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

    start_stage: PipelineStage
    """Start stage of the pipeline to run."""

    end_stage: PipelineStage
    """End stage of the pipeline to run."""

    pipeline_entity_id: str | None = None
    """Id of the entity with which pipeline to run."""

    announce_text: str | None = None
    """Text to announce using text-to-speech."""

    announce_media_id: str | None = None
    """Media id to announce."""
