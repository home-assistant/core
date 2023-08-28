"""TOLO Sauna fan controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fan controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ToloFan(coordinator, entry)])


class ToloFan(ToloSaunaCoordinatorEntity, FanEntity):
    """Sauna fan control."""

    _attr_translation_key = "fan"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO fan entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_fan"

    @property
    def is_on(self) -> bool:
        """Return if sauna fan is running."""
        return self.coordinator.data.status.fan_on

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on sauna fan."""
        self.coordinator.client.set_fan_on(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off sauna fan."""
        self.coordinator.client.set_fan_on(False)
