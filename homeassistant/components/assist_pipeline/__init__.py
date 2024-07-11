"""The Assist pipeline integration."""

from __future__ import annotations

from collections.abc import AsyncIterable

import voluptuous as vol

from homeassistant.components import stt
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEBUG_RECORDING_DIR,
    DATA_CONFIG,
    DATA_LAST_WAKE_UP,
    DOMAIN,
    EVENT_RECORDING,
)
from .error import PipelineNotFound
from .pipeline import (
    AudioSettings,
    Pipeline,
    PipelineEvent,
    PipelineEventCallback,
    PipelineEventType,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    WakeWordSettings,
    async_create_default_pipeline,
    async_get_pipeline,
    async_get_pipelines,
    async_migrate_engine,
    async_run_migrations,
    async_setup_pipeline_store,
    async_update_pipeline,
)
from .websocket_api import async_register_websocket_api

__all__ = (
    "DOMAIN",
    "async_create_default_pipeline",
    "async_get_pipelines",
    "async_migrate_engine",
    "async_setup",
    "async_pipeline_from_audio_stream",
    "async_update_pipeline",
    "AudioSettings",
    "Pipeline",
    "PipelineEvent",
    "PipelineEventType",
    "PipelineNotFound",
    "WakeWordSettings",
    "EVENT_RECORDING",
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEBUG_RECORDING_DIR): str,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Assist pipeline integration."""
    hass.data[DATA_CONFIG] = config.get(DOMAIN, {})

    # wake_word_id -> timestamp of last detection (monotonic_ns)
    hass.data[DATA_LAST_WAKE_UP] = {}

    await async_setup_pipeline_store(hass)
    await async_run_migrations(hass)
    async_register_websocket_api(hass)

    return True


async def async_pipeline_from_audio_stream(
    hass: HomeAssistant,
    *,
    context: Context,
    event_callback: PipelineEventCallback,
    stt_metadata: stt.SpeechMetadata,
    stt_stream: AsyncIterable[bytes],
    wake_word_phrase: str | None = None,
    pipeline_id: str | None = None,
    conversation_id: str | None = None,
    tts_audio_output: str | None = None,
    wake_word_settings: WakeWordSettings | None = None,
    audio_settings: AudioSettings | None = None,
    device_id: str | None = None,
    start_stage: PipelineStage = PipelineStage.STT,
    end_stage: PipelineStage = PipelineStage.TTS,
) -> None:
    """Create an audio pipeline from an audio stream.

    Raises PipelineNotFound if no pipeline is found.
    """
    pipeline_input = PipelineInput(
        conversation_id=conversation_id,
        device_id=device_id,
        stt_metadata=stt_metadata,
        stt_stream=stt_stream,
        wake_word_phrase=wake_word_phrase,
        run=PipelineRun(
            hass,
            context=context,
            pipeline=async_get_pipeline(hass, pipeline_id=pipeline_id),
            start_stage=start_stage,
            end_stage=end_stage,
            event_callback=event_callback,
            tts_audio_output=tts_audio_output,
            wake_word_settings=wake_word_settings,
            audio_settings=audio_settings or AudioSettings(),
        ),
    )
    await pipeline_input.validate()
    await pipeline_input.execute()
