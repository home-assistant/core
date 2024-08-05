"""Base class for assist satellite entities."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from enum import IntFlag, StrEnum, auto
import logging

from homeassistant.components import stt
from homeassistant.components.assist_pipeline.pipeline import PipelineStage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SatelliteCapabilities:
    """Capabilities of satellite"""

    has_vad: bool
    """True if on-device VAD is supported"""

    wake_words: list[str]
    """Available on-device wake words"""

    max_active_wake_words: int | None
    """Maximum number of active wake words"""

    @property
    def has_wake_word(self) -> bool:
        """True when device can do on-device wake word detection"""
        return bool(self.wake_words)


@dataclass
class SatelliteConfig:
    """Configuration of satellite"""

    active_wake_words: list[str]
    """List of wake words that should be active (empty = streaming)"""

    finished_speaking_seconds: float | None
    """Seconds of silence before voice command is finished (on-device VAD only)"""


@dataclass
class PipelineRunConfig:
    """Configuration for a satellite pipeline run"""

    wake_word_names: list[str] | None
    """Wake word names to listen for (start_stage = wake)."""

    announce_text: str | None
    """Text to announce using text-to-speech (start_stage = tts)"""

    announce_url: str | None
    """Media URL to announce (start_stage = tts)"""


@dataclass
class PipelineRunResult:
    """Result of a pipeline run"""

    detected_wake_word: str | None
    """Name of detected wake word (None if timeout)"""

    command_text: str | None
    """Transcript of speech-to-text for voice command"""


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of the satellite entity."""

    AUDIO_INPUT = auto()
    """Satellite is capable of recording and streaming audio to Home Assistant."""

    AUDIO_OUTPUT = auto()
    """Satellite is capable of playing audio."""

    WAKE_WORD = auto()
    """Satellite is capable of on-device wake word detection."""

    VOICE_ACTIVITY_DETECTION = auto()
    """Satellite is capable of on-device VAD."""

    TRIGGER = auto()
    """Satellite supports remotely triggering pipelines."""


class AssistSatelliteState(StrEnum):
    """Valid states of an Assist satellite entity."""

    IDLE = "idle"
    """Device is waiting for the wake word."""

    LISTENING = "listening"
    """Device is streaming audio with the command to Home Assistant."""

    PROCESSING = "processing"
    """Device has stopped streaming audio and is waiting for Home Assistant to process the voice command."""

    RESPONDING = "responding"
    """Device is speaking the response."""

    TIMER_RINGING = "timer_ringing"
    """Device is notifying the user that a timer has elapsed."""

    MUTED = "muted"
    """Device is muted (in software or hardware)."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DOMAIN] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class AssistSatelliteEntity(entity.Entity):
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
        """Runs a pipeline on the satellite from start to end stage.

        Can be called from a service.

        - announce when start/end = "tts"
        - listen for wake word when start/end = "wake"
        - listen for command when start/end = "stt" (no processing)
        - listen for command when start = "stt", end = "tts" (with processing)
        """
        raise NotImplementedError

    async def _async_accept_pipeline_from_satellite(
        self, stt_stream: AsyncIterable[bytes], stt_metadata: stt.SpeechMetadata
    ) -> PipelineRunResult | None:
        """Called by the platform when the voice satellite detected a wake word and
        wants to trigger an assist pipeline in Home Assistant.
        """
        raise NotImplementedError

    @property
    def satellite_capabilities(self) -> SatelliteCapabilities:
        """Get satellite capabilitites"""
        raise NotImplementedError

    async def async_get_config(self) -> SatelliteConfig:
        """Get satellite configuration"""
        raise NotImplementedError

    async def async_set_config(self, config: SatelliteConfig) -> None:
        """Set satellite configuration"""
        raise NotImplementedError

    @abstractmethod
    async def _async_config_updated(self) -> None:
        """Callback called when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """
        raise NotImplementedError

    @property
    def is_muted(self) -> bool:
        """Return if the satellite is muted."""
        raise NotImplementedError

    @abstractmethod
    async def async_set_mute(self, mute: bool) -> None:
        """Mute or unmute the satellite."""
        raise NotImplementedError
