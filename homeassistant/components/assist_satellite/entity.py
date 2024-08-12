"""Assist satellite entity."""

from abc import abstractmethod
from collections.abc import AsyncIterable

from homeassistant.components.assist_pipeline import (
    PipelineEventCallback,
    PipelineStage,
)
from homeassistant.const import EntityCategory
from homeassistant.core import Context
from homeassistant.helpers import entity
from homeassistant.helpers.entity import EntityDescription

from .models import AssistSatelliteEntityFeature, AssistSatelliteState, SatelliteConfig


class AssistSatelliteEntity(entity.Entity):
    """Entity encapsulating the state and functionality of an Assist satellite."""

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

    def __init__(self) -> None:
        """Initialize Assist satellite entity."""
        self.satellite_config = SatelliteConfig()
        super().__init__()

    @abstractmethod
    async def _async_accept_pipeline_from_satellite(
        self,
        context: Context,
        event_callback: PipelineEventCallback,
        audio_stream: AsyncIterable[bytes],
        start_stage: PipelineStage = PipelineStage.STT,
        end_stage: PipelineStage = PipelineStage.TTS,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Triggers an Assist pipeline in Home Assistant from a satellite."""

    async def async_get_config(self) -> SatelliteConfig:
        """Get satellite configuration."""
        return self.satellite_config

    async def async_set_config(self, config: SatelliteConfig) -> None:
        """Set satellite configuration."""
        self.satellite_config = config
        await self._async_config_updated()

    @abstractmethod
    async def _async_config_updated(self) -> None:
        """Inform when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """

    @property
    def is_microphone_muted(self) -> bool:
        """Return if the satellite's microphone is muted."""
        return self._attr_state == AssistSatelliteState.MUTED

    @abstractmethod
    async def async_set_microphone_mute(self, mute: bool) -> None:
        """Mute or unmute the satellite's microphone."""
