"""The Assist pipeline integration."""
from __future__ import annotations

from collections.abc import AsyncIterable

from homeassistant.components import stt, wake
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
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
    "PipelineNotFound",
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
    device_id: str | None = None,
) -> None:
    """Create an audio pipeline from an audio stream.

    Raises PipelineNotFound if no pipeline is found.
    """
    pipeline_input = PipelineInput(
        conversation_id=conversation_id,
        device_id=device_id,
        stt_metadata=stt_metadata,
        stt_stream=stt_stream,
        run=PipelineRun(
            hass,
            context=context,
            pipeline=async_get_pipeline(hass, pipeline_id=pipeline_id),
            start_stage=PipelineStage.STT,
            end_stage=PipelineStage.TTS,
            event_callback=event_callback,
            tts_audio_output=tts_audio_output,
        ),
    )
    await pipeline_input.validate()
    await pipeline_input.execute()


async def async_pipeline_detect_wake_word(
    hass: HomeAssistant,
    context: Context,
    audio_stream: AsyncIterable[bytes],
    pipeline_id: str | None = None,
) -> wake.DetectionResult | None:
    """Detect wake word for a pipeline in an audio stream.

    Audio must be 16Khz mono with 16-bit PCM samples.
    """
    # Not added to pipeline just yet
    # pipeline = async_get_pipeline(hass, pipeline_id)
    # wake_engine_id = pipeline.wake_engine or wake.async_default_engine(hass)
    wake_engine_id = wake.async_default_engine(hass)
    if wake_engine_id is None:
        raise ValueError("No wake word engine")

    wake_engine = wake.async_get_wake_word_detection_entity(hass, wake_engine_id)
    if wake_engine is None:
        raise ValueError(f"Invalid wake engine id: {wake_engine_id}")

    async def timestamped_stream() -> AsyncIterable[tuple[bytes, int]]:
        """Yield audio with timestamps (milliseconds since start of stream)."""
        timestamp = 0
        async for chunk in audio_stream:
            yield chunk, timestamp
            timestamp += (len(chunk) // 2) // 16  # milliseconds @ 16Khz

    result = await wake_engine.async_process_audio_stream(timestamped_stream())
    return result
