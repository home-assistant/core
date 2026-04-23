"""Text platform for Tessie integration."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie Text platform from a config entry."""
    async_add_entities(
        TessieNavigationTextEntity(vehicle) for vehicle in entry.runtime_data.vehicles
    )


class TessieNavigationTextEntity(TessieEntity, TextEntity):
    """Text entity to send a navigation destination to the vehicle."""

    _attr_mode = TextMode.TEXT
    _attr_native_max = 255
    _attr_native_min = 1
    _attr_native_value: str | None = None

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the navigation text entity."""
        super().__init__(vehicle, "navigation_destination")

    async def async_set_value(self, value: str) -> None:
        """Send a navigation destination to the vehicle."""
        await self.run(self.api.navigation_request(value))
