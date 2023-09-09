"""TOLO Sauna Select controls."""

from __future__ import annotations

from tololib.const import LampMode

from homeassistant.components.select import SelectEntity
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
    """Set up select entities for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ToloLampModeSelect(coordinator, entry)])


class ToloLampModeSelect(ToloSaunaCoordinatorEntity, SelectEntity):
    """TOLO Sauna lamp mode select."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lightbulb-multiple-outline"
    _attr_options = [lamp_mode.name.lower() for lamp_mode in LampMode]
    _attr_translation_key = "lamp_mode"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize lamp mode select entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_lamp_mode"

    @property
    def current_option(self) -> str:
        """Return current lamp mode."""
        return self.coordinator.data.settings.lamp_mode.name.lower()

    def select_option(self, option: str) -> None:
        """Select lamp mode."""
        self.coordinator.client.set_lamp_mode(LampMode[option.upper()])
