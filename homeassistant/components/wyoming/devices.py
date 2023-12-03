"""Class to manage satellite devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


@dataclass
class SatelliteDevice:
    """Class to store device."""

    satellite_id: str
    device_id: str
    is_active: bool = False
    is_enabled: bool = True
    update_listeners: list[Callable[[SatelliteDevice], None]] = field(
        default_factory=list
    )

    @callback
    def set_is_active(self, active: bool) -> None:
        """Set active state."""
        self.is_active = active
        for listener in self.update_listeners:
            listener(self)

    @callback
    def set_is_enabled(self, enabled: bool) -> None:
        """Set enabled state."""
        self.is_enabled = enabled
        for listener in self.update_listeners:
            listener(self)

    @callback
    def async_pipeline_changed(self) -> None:
        """Inform listeners that pipeline selection has changed."""
        for listener in self.update_listeners:
            listener(self)

    @callback
    def async_listen_update(
        self, listener: Callable[[SatelliteDevice], None]
    ) -> Callable[[], None]:
        """Listen for updates."""
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)

    def get_assist_in_progress_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for assist in progress binary sensor."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{self.satellite_id}-assist_in_progress"
        )

    def get_satellite_enabled_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for satellite enabled switch."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "switch", DOMAIN, f"{self.satellite_id}-satellite_enabled"
        )

    def get_pipeline_entity_id(self, hass: HomeAssistant) -> str | None:
        """Return entity id for pipeline select."""
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{self.satellite_id}-pipeline"
        )
