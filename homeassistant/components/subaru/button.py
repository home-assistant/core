"""Support for Subaru remote service buttons."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from subarulink import Controller as SubaruAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import get_device_info
from .const import (
    SERVICE_REMOTE_START,
    SERVICE_REMOTE_STOP,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_VIN,
)
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator
from .remote_service import async_call_remote_service


@dataclass(frozen=True, kw_only=True)
class SubaruButtonEntityDescription(ButtonEntityDescription):
    """Describes a Subaru button entity."""

    arg: Callable[[dict[str, Any]], str | None] | None = None


REMOTE_BUTTONS = [
    SubaruButtonEntityDescription(
        key=SERVICE_REMOTE_START,
        translation_key="remote_start",
        arg=lambda _: "Auto",
    ),
    SubaruButtonEntityDescription(
        key=SERVICE_REMOTE_STOP,
        translation_key="remote_stop",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SubaruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru remote service buttons by config_entry."""
    coordinator = config_entry.runtime_data.coordinator
    controller = config_entry.runtime_data.controller
    vehicle_info = config_entry.runtime_data.vehicles
    async_add_entities(
        SubaruButton(vehicle, controller, coordinator, description)
        for vehicle in vehicle_info.values()
        if vehicle[VEHICLE_HAS_REMOTE_START] or vehicle[VEHICLE_HAS_EV]
        for description in REMOTE_BUTTONS
    )


class SubaruButton(ButtonEntity):
    """Class for a Subaru button."""

    _attr_has_entity_name = True
    entity_description: SubaruButtonEntityDescription

    def __init__(
        self,
        vehicle_info: dict[str, Any],
        controller: SubaruAPI,
        coordinator: SubaruDataUpdateCoordinator,
        description: SubaruButtonEntityDescription,
    ) -> None:
        """Initialize the button for the vehicle."""
        self.controller = controller
        self.coordinator = coordinator
        self.vehicle_info = vehicle_info
        self.entity_description = description
        vin = vehicle_info[VEHICLE_VIN]
        self._attr_unique_id = f"{vin}_{description.key}"
        self._attr_device_info = get_device_info(vehicle_info)

    async def async_press(self) -> None:
        """Press the button."""
        arg = (
            self.entity_description.arg(self.vehicle_info)
            if self.entity_description.arg
            else None
        )
        await async_call_remote_service(
            self.controller,
            self.entity_description.key,
            self.vehicle_info,
            arg,
        )
        await self.coordinator.async_refresh()
