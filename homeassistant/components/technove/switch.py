"""Support for TechnoVE switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity
from .helpers import technove_exception_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TechnoVE switch based on a config entry."""
    coordinator: TechnoVEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            TechnoVEAutoChargeSwitch(coordinator),
        ]
    )


class TechnoVEAutoChargeSwitch(TechnoVEEntity, SwitchEntity):
    """Defines a TechnoVE auto-charge switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "auto_charge"
    _segment: int

    def __init__(self, coordinator: TechnoVEDataUpdateCoordinator) -> None:
        """Initialize TechnoVE auto-charge switch."""
        super().__init__(coordinator, "auto_charge")

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.info.auto_charge)

    @technove_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the TechnoVE reverse effect switch."""
        await self.coordinator.technove.set_auto_charge(enabled=False)

    @technove_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the TechnoVE reverse effect switch."""
        await self.coordinator.technove.set_auto_charge(enabled=True)
