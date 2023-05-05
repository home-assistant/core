"""The Assist pipeline integration."""
from __future__ import annotations

from collections.abc import AsyncIterable

from homeassistant.components import stt
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .error import PipelineNotFound
from .pipeline import (
    Pipeline,
    PipelineEvent,
    PipelineEventCallback,
    PipelineEventType,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    async_create_default_pipeline,
    async_get_pipeline,
    async_get_pipelines,
    async_setup_pipeline_store,
)
from .websocket_api import async_register_websocket_api

__all__ = (
    "DOMAIN",
    "async_create_default_pipeline",
    "async_get_pipelines",
    "async_setup",
    "async_pipeline_from_audio_stream",
    "Pipeline",
    "PipelineEvent",
    "PipelineEventType",
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Assist pipeline integration."""
    await async_setup_pipeline_store(hass)
    async_register_websocket_api(hass)

    return True


async def async_pipeline_from_audio_stream(
    hass: HomeAssistant,
    context: Context,
    event_callback: PipelineEventCallback,
    stt_metadata: stt.SpeechMetadata,
    stt_stream: AsyncIterable[bytes],
    pipeline_id: str | None = None,
    conversation_id: str | None = None,
    tts_audio_output: str | None = None,
) -> None:
    """Create an audio pipeline from an audio stream."""
    pipeline = async_get_pipeline(hass, pipeline_id=pipeline_id)
    if pipeline is None:
        raise PipelineNotFound(
            "pipeline_not_found", f"Pipeline {pipeline_id} not found"
        )

    pipeline_input = PipelineInput(
        conversation_id=conversation_id,
        stt_metadata=stt_metadata,
        stt_stream=stt_stream,
        run=PipelineRun(
            hass,
            context=context,
            pipeline=pipeline,
            start_stage=PipelineStage.STT,
            end_stage=PipelineStage.TTS,
            event_callback=event_callback,
            tts_audio_output=tts_audio_output,
        ),
    )

    await pipeline_input.validate()
    await pipeline_input.execute()
