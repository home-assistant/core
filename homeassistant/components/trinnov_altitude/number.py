"""Number entities for Trinnov Altitude integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode

from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities from config entry."""
    async_add_entities([TrinnovAltitudeVolumeNumber(entry.runtime_data)])


class TrinnovAltitudeVolumeNumber(TrinnovAltitudeEntity, NumberEntity):
    """Volume number entity."""

    _attr_name = None
    _attr_native_min_value = -120.0
    _attr_native_max_value = 20.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.SLIDER
    _attr_translation_key = "volume"

    @property
    def native_value(self) -> float | None:
        """Return current volume."""
        return self._device.state.volume

    async def async_set_native_value(self, value: float) -> None:
        """Set volume value."""
        await self._device.volume_set(value)
