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

    _is_active_listener: Callable[[], None] | None = None
    _is_muted_listener: Callable[[], None] | None = None
    _pipeline_listener: Callable[[], None] | None = None

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
