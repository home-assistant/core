"""Support for Subaru remote service buttons."""

from __future__ import annotations

from typing import Any

from subarulink import Controller as SubaruAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, get_device_info
from .const import (
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    SERVICE_REMOTE_START,
    SERVICE_REMOTE_STOP,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_VIN,
)
from .coordinator import SubaruDataUpdateCoordinator
from .remote_service import async_call_remote_service

REMOTE_BUTTONS = [
    ButtonEntityDescription(
        key=SERVICE_REMOTE_START,
        translation_key="remote_start",
    ),
    ButtonEntityDescription(
        key=SERVICE_REMOTE_STOP,
        translation_key="remote_stop",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru remote service buttons by config_entry."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry[ENTRY_COORDINATOR]
    controller = entry[ENTRY_CONTROLLER]
    vehicle_info = entry[ENTRY_VEHICLES]
    async_add_entities(
        SubaruButton(vehicle, controller, coordinator, description)
        for vehicle in vehicle_info.values()
        if vehicle[VEHICLE_HAS_REMOTE_START] or vehicle[VEHICLE_HAS_EV]
        for description in REMOTE_BUTTONS
    )


class SubaruButton(ButtonEntity):
    """Class for a Subaru button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle_info: dict[str, Any],
        controller: SubaruAPI,
        coordinator: SubaruDataUpdateCoordinator,
        description: ButtonEntityDescription,
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
        # Default to "Auto" until a climate preset selector entity is added
        arg = "Auto" if self.entity_description.key == SERVICE_REMOTE_START else None
        await async_call_remote_service(
            self.controller,
            self.entity_description.key,
            self.vehicle_info,
            arg,
        )
        await self.coordinator.async_refresh()
