"""The Voice Assistant integration."""
from __future__ import annotations

from collections.abc import AsyncIterable

from homeassistant.components import stt
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .error import PipelineNotFound
from .pipeline import (
    PipelineEvent,
    PipelineEventCallback,
    PipelineEventType,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    async_get_pipeline,
    async_setup_pipeline_store,
)
from .websocket_api import async_register_websocket_api

__all__ = (
    "DOMAIN",
    "async_setup",
    "async_pipeline_from_audio_stream",
    "PipelineEvent",
    "PipelineEventType",
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Voice Assistant integration."""
    await async_setup_pipeline_store(hass)
    async_register_websocket_api(hass)

    return True


async def async_pipeline_from_audio_stream(
    hass: HomeAssistant,
    event_callback: PipelineEventCallback,
    stt_metadata: stt.SpeechMetadata,
    stt_stream: AsyncIterable[bytes],
    language: str | None = None,
    pipeline_id: str | None = None,
    conversation_id: str | None = None,
    context: Context | None = None,
) -> None:
    """Create an audio pipeline from an audio stream."""
    if language is None:
        language = hass.config.language

    # Temporary workaround for language codes
    if language == "en":
        language = "en-US"

    if stt_metadata.language == "":
        stt_metadata.language = language

    if context is None:
        context = Context()

    pipeline = await async_get_pipeline(
        hass,
        pipeline_id=pipeline_id,
        language=language,
    )
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
        ),
    )

    await pipeline_input.validate()
    await pipeline_input.execute()
