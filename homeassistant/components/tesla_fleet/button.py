"""Button platform for Tesla Fleet integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tesla_fleet_api.const import Scope

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

PARALLEL_UPDATES = 0


async def do_nothing() -> dict[str, dict[str, bool]]:
    """Do nothing with a positive result."""
    return {"response": {"result": True}}


@dataclass(frozen=True, kw_only=True)
class TeslaFleetButtonEntityDescription(ButtonEntityDescription):
    """Describes a TeslaFleet Button entity."""

    func: Callable[[TeslaFleetButtonEntity], Awaitable[Any]]


DESCRIPTIONS: tuple[TeslaFleetButtonEntityDescription, ...] = (
    TeslaFleetButtonEntityDescription(
        key="wake", func=lambda self: do_nothing()
    ),  # Every button runs wakeup, so func does nothing
    TeslaFleetButtonEntityDescription(
        key="flash_lights", func=lambda self: self.api.flash_lights()
    ),
    TeslaFleetButtonEntityDescription(
        key="honk", func=lambda self: self.api.honk_horn()
    ),
    TeslaFleetButtonEntityDescription(
        key="enable_keyless_driving", func=lambda self: self.api.remote_start_drive()
    ),
    TeslaFleetButtonEntityDescription(
        key="boombox", func=lambda self: self.api.remote_boombox(0)
    ),
    TeslaFleetButtonEntityDescription(
        key="homelink",
        func=lambda self: self.api.trigger_homelink(
            lat=self.coordinator.data["drive_state_latitude"],
            lon=self.coordinator.data["drive_state_longitude"],
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaFleet Button platform from a config entry."""

    async_add_entities(
        TeslaFleetButtonEntity(vehicle, description)
        for vehicle in entry.runtime_data.vehicles
        for description in DESCRIPTIONS
        if Scope.VEHICLE_CMDS in entry.runtime_data.scopes
    )


class TeslaFleetButtonEntity(TeslaFleetVehicleEntity, ButtonEntity):
    """Base class for TeslaFleet buttons."""

    entity_description: TeslaFleetButtonEntityDescription

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        description: TeslaFleetButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.entity_description.func(self))
