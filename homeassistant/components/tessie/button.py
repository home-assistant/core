"""Button platform for Tessie integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tesla_fleet_api.tessie import Vehicle

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TessieButtonEntityDescription(ButtonEntityDescription):
    """Describes a Tessie Button entity."""

    func: Callable[[Vehicle], Awaitable[dict[str, Any]]]


DESCRIPTIONS: tuple[TessieButtonEntityDescription, ...] = (
    TessieButtonEntityDescription(key="wake", func=lambda api: api.wake()),
    TessieButtonEntityDescription(key="flash_lights", func=lambda api: api.flash()),
    TessieButtonEntityDescription(key="honk", func=lambda api: api.honk()),
    TessieButtonEntityDescription(
        key="trigger_homelink",
        func=lambda api: api.tessie_trigger_homelink(),
    ),
    TessieButtonEntityDescription(
        key="enable_keyless_driving",
        func=lambda api: api.remote_start(),
    ),
    TessieButtonEntityDescription(key="boombox", func=lambda api: api.remote_boombox()),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie Button platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        TessieButtonEntity(vehicle, description)
        for vehicle in data.vehicles
        for description in DESCRIPTIONS
    )


class TessieButtonEntity(TessieEntity, ButtonEntity):
    """Base class for Tessie Buttons."""

    entity_description: TessieButtonEntityDescription

    def __init__(
        self,
        vehicle: TessieVehicleData,
        description: TessieButtonEntityDescription,
    ) -> None:
        """Initialize the Button."""
        super().__init__(vehicle, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        await self.run(self.entity_description.func(self.api))
