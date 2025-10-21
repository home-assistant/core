"""The Assist pipeline integration."""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.components import stt
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEBUG_RECORDING_DIR,
    DATA_CONFIG,
    DATA_LAST_WAKE_UP,
    DOMAIN,
    EVENT_RECORDING,
    OPTION_PREFERRED,
    SAMPLE_CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    SAMPLES_PER_CHUNK,
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
    async_setup_pipeline_store,
    async_update_pipeline,
)
from .websocket_api import async_register_websocket_api

__all__ = (
    "DOMAIN",
    "EVENT_RECORDING",
    "OPTION_PREFERRED",
    "SAMPLES_PER_CHUNK",
    "SAMPLE_CHANNELS",
    "SAMPLE_RATE",
    "SAMPLE_WIDTH",
    "AudioSettings",
    "Pipeline",
    "PipelineEvent",
    "PipelineEventType",
    "PipelineNotFound",
    "WakeWordSettings",
    "PipelineOptions",
    "async_create_default_pipeline",
    "async_get_pipelines",
    "async_pipeline_from_audio_stream",
    "async_setup",
    "async_update_pipeline",
)


@dataclass(slots=True)
class PipelineOptions:
    """Options to configure an Assist pipeline run from audio stream.

    This groups optional parameters to keep function signatures small and stable.
    """

    wake_word_phrase: str | None = None
    pipeline_id: str | None = None
    conversation_id: str | None = None
    tts_audio_output: str | dict[str, Any] | None = None
    wake_word_settings: WakeWordSettings | None = None
    audio_settings: AudioSettings | None = None
    device_id: str | None = None
    satellite_id: str | None = None
    start_stage: PipelineStage = PipelineStage.STT
    end_stage: PipelineStage = PipelineStage.TTS
    conversation_extra_system_prompt: str | None = None

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


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Assist pipeline integration."""
    hass.data[DATA_CONFIG] = _config.get(DOMAIN, {})

    # wake_word_id -> timestamp of last detection (monotonic_ns)
    hass.data[DATA_LAST_WAKE_UP] = {}

    await async_setup_pipeline_store(hass)
    async_register_websocket_api(hass)

    return True


async def async_pipeline_from_audio_stream(
    hass: HomeAssistant,
    *,
    context: Context,
    event_callback: PipelineEventCallback,
    stt_metadata: stt.SpeechMetadata,
    stt_stream: AsyncIterable[bytes],
    options: PipelineOptions | None = None,
    **legacy_kwargs: Any,
) -> None:
    """Create an audio pipeline from an audio stream.

    Raises PipelineNotFound if no pipeline is found.
    """
    # Backward-compat: support legacy keyword args when options is not provided
    if options is None:
        options = PipelineOptions(
            wake_word_phrase=legacy_kwargs.get("wake_word_phrase"),
            pipeline_id=legacy_kwargs.get("pipeline_id"),
            conversation_id=legacy_kwargs.get("conversation_id"),
            tts_audio_output=legacy_kwargs.get("tts_audio_output"),
            wake_word_settings=legacy_kwargs.get("wake_word_settings"),
            audio_settings=legacy_kwargs.get("audio_settings"),
            device_id=legacy_kwargs.get("device_id"),
            satellite_id=legacy_kwargs.get("satellite_id"),
            start_stage=legacy_kwargs.get("start_stage", PipelineStage.STT),
            end_stage=legacy_kwargs.get("end_stage", PipelineStage.TTS),
            conversation_extra_system_prompt=legacy_kwargs.get(
                "conversation_extra_system_prompt"
            ),
        )

    with chat_session.async_get_chat_session(hass, options.conversation_id) as session:
        pipeline_input = PipelineInput(
            session=session,
            device_id=options.device_id,
            satellite_id=options.satellite_id,
            stt_metadata=stt_metadata,
            stt_stream=stt_stream,
            wake_word_phrase=options.wake_word_phrase,
            conversation_extra_system_prompt=options.conversation_extra_system_prompt,
            run=PipelineRun(
                hass,
                context=context,
                pipeline=async_get_pipeline(hass, pipeline_id=options.pipeline_id),
                start_stage=options.start_stage,
                end_stage=options.end_stage,
                event_callback=event_callback,
                tts_audio_output=options.tts_audio_output,
                wake_word_settings=options.wake_word_settings,
                audio_settings=options.audio_settings or AudioSettings(),
            ),
        )
        await pipeline_input.validate()
        await pipeline_input.execute()
