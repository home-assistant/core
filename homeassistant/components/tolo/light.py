"""TOLO Sauna light controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ToloSaunaUpdateCoordinator
from .entity import ToloSaunaCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ToloLight(coordinator, entry)])


class ToloLight(ToloSaunaCoordinatorEntity, LightEntity):
    """Sauna light control."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_translation_key = "light"
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna Light entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_light"

    @property
    def is_on(self) -> bool:
        """Return current lamp status."""
        return self.coordinator.data.status.lamp_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on TOLO Sauna lamp."""
        self.coordinator.client.set_lamp_on(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off TOLO Sauna lamp."""
        self.coordinator.client.set_lamp_on(False)
