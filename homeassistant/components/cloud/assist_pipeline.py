"""Handle Cloud assist pipelines."""

from typing import Any

from homeassistant.components.assist_pipeline import (
    async_get_pipelines,
    async_setup_pipeline_store,
    async_update_pipeline,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_PLATFORMS_SETUP, DOMAIN


async def async_migrate_cloud_pipeline_engine(
    hass: HomeAssistant, platform: Platform, engine_id: str
) -> None:
    """Migrate the pipeline engines in the cloud assist pipeline."""
    # Migrate existing pipelines with cloud stt or tts to use new cloud engine id.
    # Added in 2024.02.0. Can be removed in 2025.02.0.

    # We need to make sure that both stt and tts are loaded before this migration.
    # Assist pipeline will call default engine when setting up the store.
    # Wait for the stt or tts platform loaded event here.
    if platform == Platform.STT:
        wait_for_platform = Platform.TTS
        pipeline_attribute = "stt_engine"
    elif platform == Platform.TTS:
        wait_for_platform = Platform.STT
        pipeline_attribute = "tts_engine"
    else:
        raise ValueError(f"Invalid platform {platform}")

    platforms_setup = hass.data[DATA_PLATFORMS_SETUP]
    await platforms_setup[wait_for_platform].wait()

    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    kwargs: dict[str, Any] = {pipeline_attribute: engine_id}
    pipelines = async_get_pipelines(hass)
    for pipeline in pipelines:
        if getattr(pipeline, pipeline_attribute) == DOMAIN:
            await async_update_pipeline(hass, pipeline, **kwargs)
