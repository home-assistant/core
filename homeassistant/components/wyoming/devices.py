"""Class to manage satellite devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


@dataclass
class SatelliteDevice:
    """Class to store device."""

    satellite_id: str
    device_id: str
    is_active: bool = False
    is_muted: bool = False
    pipeline_name: str | None = None
    noise_suppression_level: int = 0
    auto_gain: int = 0
    volume_multiplier: float = 1.0

    _is_active_listener: Callable[[], None] | None = None
    _is_muted_listener: Callable[[], None] | None = None
    _pipeline_listener: Callable[[], None] | None = None
    _audio_settings_listener: Callable[[], None] | None = None

    @callback
    def set_is_active(self, active: bool) -> None:
        """Set active state."""
        if active != self.is_active:
            self.is_active = active
            if self._is_active_listener is not None:
                self._is_active_listener()

    @callback
    def set_is_muted(self, muted: bool) -> None:
        """Set muted state."""
        if muted != self.is_muted:
            self.is_muted = muted
            if self._is_muted_listener is not None:
                self._is_muted_listener()

    @callback
    def set_pipeline_name(self, pipeline_name: str) -> None:
        """Inform listeners that pipeline selection has changed."""
        if pipeline_name != self.pipeline_name:
            self.pipeline_name = pipeline_name
            if self._pipeline_listener is not None:
                self._pipeline_listener()

    @callback
    def set_noise_suppression_level(self, noise_suppression_level: int) -> None:
        """Set noise suppression level."""
        if noise_suppression_level != self.noise_suppression_level:
            self.noise_suppression_level = noise_suppression_level
            if self._audio_settings_listener is not None:
                self._audio_settings_listener()

    @callback
    def set_auto_gain(self, auto_gain: int) -> None:
        """Set auto gain amount."""
        if auto_gain != self.auto_gain:
            self.auto_gain = auto_gain
            if self._audio_settings_listener is not None:
                self._audio_settings_listener()

    @callback
    def set_volume_multiplier(self, volume_multiplier: float) -> None:
        """Set auto gain amount."""
        if volume_multiplier != self.volume_multiplier:
            self.volume_multiplier = volume_multiplier
            if self._audio_settings_listener is not None:
                self._audio_settings_listener()

    @callback
    def set_is_active_listener(self, is_active_listener: Callable[[], None]) -> None:
        """Listen for updates to is_active."""
        self._is_active_listener = is_active_listener

    @callback
    def set_is_muted_listener(self, is_muted_listener: Callable[[], None]) -> None:
        """Listen for updates to muted status."""
        self._is_muted_listener = is_muted_listener

    @callback
    def set_pipeline_listener(self, pipeline_listener: Callable[[], None]) -> None:
        """Listen for updates to pipeline."""
        self._pipeline_listener = pipeline_listener

    @callback
    def set_audio_settings_listener(
        self, audio_settings_listener: Callable[[], None]
    ) -> None:
        """Listen for updates to audio settings."""
        self._audio_settings_listener = audio_settings_listener

    def get_assist_in_progress_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for assist in progress binary sensor."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{self.satellite_id}-assist_in_progress"
        )

    def get_muted_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for satellite muted switch."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "switch", DOMAIN, f"{self.satellite_id}-mute"
        )

    def get_pipeline_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for pipeline select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-pipeline"
        )

    def get_noise_suppression_level_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for noise suppression select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-noise_suppression_level"
        )

    def get_auto_gain_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for auto gain amount."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "number", DOMAIN, f"{self.satellite_id}-auto_gain"
        )

    def get_volume_multiplier_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for microphone volume multiplier."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "number", DOMAIN, f"{self.satellite_id}-volume_multiplier"
        )
