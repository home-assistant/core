"""Button platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tesla_fleet_api.const import Scope

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryButtonEntityDescription(ButtonEntityDescription):
    """Describes a Teslemetry Button entity."""

    func: Callable[[TeslemetryButtonEntity], Awaitable[Any]] | None = None


DESCRIPTIONS: tuple[TeslemetryButtonEntityDescription, ...] = (
    TeslemetryButtonEntityDescription(key="wake"),  # Every button runs wakeup
    TeslemetryButtonEntityDescription(
        key="flash_lights", func=lambda self: self.api.flash_lights()
    ),
    TeslemetryButtonEntityDescription(
        key="honk", func=lambda self: self.api.honk_horn()
    ),
    TeslemetryButtonEntityDescription(
        key="enable_keyless_driving", func=lambda self: self.api.remote_start_drive()
    ),
    TeslemetryButtonEntityDescription(
        key="boombox", func=lambda self: self.api.remote_boombox(0)
    ),
    TeslemetryButtonEntityDescription(
        key="homelink",
        func=lambda self: self.api.trigger_homelink(
            lat=self.coordinator.data["drive_state_latitude"],
            lon=self.coordinator.data["drive_state_longitude"],
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry Button platform from a config entry."""

    async_add_entities(
        TeslemetryButtonEntity(vehicle, description)
        for vehicle in entry.runtime_data.vehicles
        for description in DESCRIPTIONS
        if Scope.VEHICLE_CMDS in entry.runtime_data.scopes
    )


class TeslemetryButtonEntity(TeslemetryVehicleEntity, ButtonEntity):
    """Base class for Teslemetry buttons."""

    entity_description: TeslemetryButtonEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self.wake_up_if_asleep()
        if self.entity_description.func:
            await handle_vehicle_command(self.entity_description.func(self))
