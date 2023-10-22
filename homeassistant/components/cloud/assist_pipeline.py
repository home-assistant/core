"""Handle Cloud assist pipelines."""
from homeassistant.components.assist_pipeline import (
    async_create_default_pipeline,
    async_get_pipelines,
    async_setup_pipeline_store,
    async_update_pipeline,
)
from homeassistant.components.conversation import HOME_ASSISTANT_AGENT
from homeassistant.components.stt import DOMAIN as STT_DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN, STT_ENTITY_UNIQUE_ID


async def async_migrate_cloud_pipeline_stt_engine(
    hass: HomeAssistant, stt_engine_id: str
) -> None:
    """Migrate the speech-to-text engine in the cloud assist pipeline."""
    # Migrate existing pipelines with cloud stt to use new cloud stt engine id.
    # Added in 2023.11.0. Can be removed in 2024.11.0.
    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud

    await async_setup_pipeline_store(hass)
    pipelines = async_get_pipelines(hass)
    for pipeline in pipelines:
        if pipeline.stt_engine != DOMAIN:
            continue
        updates = pipeline.to_json() | {"stt_engine": stt_engine_id}
        updates.pop("id")
        await async_update_pipeline(hass, pipeline, updates)


async def async_create_cloud_pipeline(hass: HomeAssistant) -> str | None:
    """Create a cloud assist pipeline."""
    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    entity_registry = er.async_get(hass)
    new_stt_engine_id = entity_registry.async_get_entity_id(
        STT_DOMAIN, DOMAIN, STT_ENTITY_UNIQUE_ID
    )

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
