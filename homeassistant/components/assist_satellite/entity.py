"""Assist satellite entity."""

from abc import abstractmethod

from homeassistant.components.assist_pipeline.pipeline import PipelineStage
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription

from .models import (
    AssistSatelliteEntityFeature,
    AssistSatelliteState,
    PipelineRunConfig,
    PipelineRunResult,
    SatelliteCapabilities,
    SatelliteConfig,
)


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of a voice satellite."""

    entity_description = EntityDescription(
        key="assist_satellite",
        translation_key="assist_satellite",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_state: AssistSatelliteState | None = None
    _attr_supported_features: AssistSatelliteEntityFeature = (
        AssistSatelliteEntityFeature(0)
    )

    async def async_run_pipeline_on_satellite(
        self,
        start_stage: PipelineStage,
        end_stage: PipelineStage,
        run_config: PipelineRunConfig,
    ) -> PipelineRunResult | None:
        """Run a pipeline on the satellite from start to end stage.

        Can be called from a service.

        - announce when start/end = "tts"
        - listen for wake word when start/end = "wake"
        - listen for command when start/end = "stt" (no processing)
        - listen for command when start = "stt", end = "tts" (with processing)
        """
        raise NotImplementedError

    @property
    def satellite_capabilities(self) -> SatelliteCapabilities:
        """Get satellite capabilitites."""
        raise NotImplementedError

    async def async_get_config(self) -> SatelliteConfig:
        """Get satellite configuration."""
        raise NotImplementedError

    async def async_set_config(self, config: SatelliteConfig) -> None:
        """Set satellite configuration."""
        raise NotImplementedError

    @abstractmethod
    async def _async_config_updated(self) -> None:
        """Inform when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """
        raise NotImplementedError

    @property
    def is_microphone_muted(self) -> bool:
        """Return if the satellite's microphone is muted."""
        raise NotImplementedError

    @abstractmethod
    async def async_set_microphone_mute(self, mute: bool) -> None:
        """Mute or unmute the satellite's microphone."""
        raise NotImplementedError
