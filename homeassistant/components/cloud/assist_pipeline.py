"""Handle Cloud assist pipelines."""
from homeassistant.components.assist_pipeline import (
    async_create_default_pipeline,
    async_get_pipelines,
    async_setup_pipeline_store,
)
from homeassistant.components.conversation import HOME_ASSISTANT_AGENT
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_create_cloud_pipeline(hass: HomeAssistant) -> str | None:
    """Create a cloud assist pipeline."""
    # Make sure the pipeline store is loaded, needed because assist_pipeline
    # is an after dependency of cloud
    await async_setup_pipeline_store(hass)

    def cloud_assist_pipeline(hass: HomeAssistant) -> str | None:
        """Return the ID of a cloud-enabled assist pipeline or None.

        Check if a cloud pipeline already exists with
        legacy cloud engine id.
        """
        for pipeline in async_get_pipelines(hass):
            if (
                pipeline.conversation_engine == HOME_ASSISTANT_AGENT
                and pipeline.stt_engine == DOMAIN
                and pipeline.tts_engine == DOMAIN
            ):
                return pipeline.id
        return None

    new_cloud_pipeline_id: str | None = None

    if (cloud_assist_pipeline(hass)) is None and (
        cloud_pipeline := await async_create_default_pipeline(
            hass,
            stt_engine_id=DOMAIN,
            tts_engine_id=DOMAIN,
            pipeline_name="Home Assistant Cloud",
        )
    ):
        new_cloud_pipeline_id = cloud_pipeline.id
    return new_cloud_pipeline_id
