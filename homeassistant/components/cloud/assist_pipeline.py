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
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .const import DATA_PLATFORMS_SETUP, DOMAIN, STT_ENTITY_UNIQUE_ID


async def async_create_cloud_pipeline(hass: HomeAssistant) -> str | None:
    """Create a cloud assist pipeline."""
    # Wait for stt and tts platforms to set up before creating the pipeline.
    platforms_setup: dict[str, asyncio.Event] = hass.data[DATA_PLATFORMS_SETUP]
    await asyncio.gather(*(event.wait() for event in platforms_setup.values()))
    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    entity_registry = er.async_get(hass)
    new_stt_engine_id = entity_registry.async_get_entity_id(
        STT_DOMAIN, DOMAIN, STT_ENTITY_UNIQUE_ID
    )
    if new_stt_engine_id is None:
        # If there's no cloud stt entity, we can't create a cloud pipeline.
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
                and pipeline.tts_engine == DOMAIN
            ):
                return pipeline.id
        return None

    if (cloud_assist_pipeline(hass)) is not None or (
        cloud_pipeline := await async_create_default_pipeline(
            hass,
            stt_engine_id=new_stt_engine_id,
            tts_engine_id=DOMAIN,
            pipeline_name="Home Assistant Cloud",
        )
    ) is None:
        return None

    return cloud_pipeline.id


async def async_migrate_cloud_pipeline_stt_engine(
    hass: HomeAssistant, stt_engine_id: str
) -> None:
    """Migrate the speech-to-text engine in the cloud assist pipeline."""
    # Migrate existing pipelines with cloud stt to use new cloud stt engine id.
    # Added in 2024.01.0. Can be removed in 2025.01.0.

    # We need to make sure that tts is loaded before this migration.
    # Assist pipeline will call default engine of tts when setting up the store.
    # Wait for the tts platform loaded event here.
    platforms_setup: dict[str, asyncio.Event] = hass.data[DATA_PLATFORMS_SETUP]
    await platforms_setup[Platform.TTS].wait()

    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    pipelines = async_get_pipelines(hass)
    for pipeline in pipelines:
        if pipeline.stt_engine != DOMAIN:
            continue
        await async_update_pipeline(hass, pipeline, stt_engine=stt_engine_id)
