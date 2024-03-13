"""TOLO Sauna switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AromaTherapyOnSwitch(coordinator, entry)])


class AromaTherapyOnSwitch(ToloSaunaCoordinatorEntity, SwitchEntity):
    """Enable/disable Aroma Therapy for TOLO Sauna."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "aroma_therapy_on"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Aroma Therapy Switch."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_aroma_therapy_on"

    @property
    def is_on(self) -> bool | None:
        """Return if Aroma Therapy is currently on."""
        return self.coordinator.data.status.aroma_therapy_on

    def turn_on(self, **kwargs: Any) -> None:
        """Enable Aroma Therapy."""
        self.coordinator.client.set_aroma_therapy_on(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Disable Aroma Therapy."""
        self.coordinator.client.set_aroma_therapy_on(False)
