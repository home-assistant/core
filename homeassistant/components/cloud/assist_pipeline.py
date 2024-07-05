"""Handle Cloud assist pipelines."""

import asyncio

from homeassistant.components.assist_pipeline import (
    async_create_default_pipeline,
    async_get_pipelines,
    async_setup_pipeline_store,
    async_update_pipeline,
)
from homeassistant.components.conversation import HOME_ASSISTANT_AGENT
from homeassistant.components.stt import DOMAIN as STT_DOMAIN
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .const import (
    DATA_PLATFORMS_SETUP,
    DOMAIN,
    STT_ENTITY_UNIQUE_ID,
    TTS_ENTITY_UNIQUE_ID,
)


async def async_create_cloud_pipeline(hass: HomeAssistant) -> str | None:
    """Create a cloud assist pipeline."""
    # Wait for stt and tts platforms to set up and entities to be added
    # before creating the pipeline.
    platforms_setup = hass.data[DATA_PLATFORMS_SETUP]
    await asyncio.gather(*(event.wait() for event in platforms_setup.values()))
    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    entity_registry = er.async_get(hass)
    new_stt_engine_id = entity_registry.async_get_entity_id(
        STT_DOMAIN, DOMAIN, STT_ENTITY_UNIQUE_ID
    )
    new_tts_engine_id = entity_registry.async_get_entity_id(
        TTS_DOMAIN, DOMAIN, TTS_ENTITY_UNIQUE_ID
    )
    if new_stt_engine_id is None or new_tts_engine_id is None:
        # If there's no cloud stt or tts entity, we can't create a cloud pipeline.
        return None

    def cloud_assist_pipeline(hass: HomeAssistant) -> str | None:
        """Return the ID of a cloud-enabled assist pipeline or None.

        Check if a cloud pipeline already exists with either
        legacy or current cloud engine ids.
        """
        for pipeline in async_get_pipelines(hass):
            if (
                pipeline.conversation_engine == HOME_ASSISTANT_AGENT
                and pipeline.stt_engine in (DOMAIN, new_stt_engine_id)
                and pipeline.tts_engine in (DOMAIN, new_tts_engine_id)
            ):
                return pipeline.id
        return None

    if (cloud_assist_pipeline(hass)) is not None or (
        cloud_pipeline := await async_create_default_pipeline(
            hass,
            stt_engine_id=new_stt_engine_id,
            tts_engine_id=new_tts_engine_id,
            pipeline_name="Home Assistant Cloud",
        )
    ) is None:
        return None

    return cloud_pipeline.id


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

    kwargs: dict[str, str] = {pipeline_attribute: engine_id}
    pipelines = async_get_pipelines(hass)
    for pipeline in pipelines:
        if getattr(pipeline, pipeline_attribute) == DOMAIN:
            await async_update_pipeline(hass, pipeline, **kwargs)
