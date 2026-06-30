"""Support for OpenEVSE button entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp.__main__ import OpenEVSE

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import ATTR_CONNECTIONS, ATTR_SERIAL_NUMBER, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator
from .helpers import openevse_exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSEButtonDescription(ButtonEntityDescription):
    """Describes an OpenEVSE button entity."""

    press_fn: Callable[[OpenEVSE], Awaitable[Any]]


BUTTON_TYPES: tuple[OpenEVSEButtonDescription, ...] = (
    OpenEVSEButtonDescription(
        key="restart_wifi",
        translation_key="restart_wifi",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda ev: ev.restart_wifi(),
    ),
    OpenEVSEButtonDescription(
        key="restart_evse",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda ev: ev.restart_evse(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE buttons based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSEButton(coordinator, description, identifier, entry.unique_id)
        for description in BUTTON_TYPES
    )


class OpenEVSEButton(CoordinatorEntity[OpenEVSEDataUpdateCoordinator], ButtonEntity):
    """Implementation of an OpenEVSE button."""

    _attr_has_entity_name = True
    entity_description: OpenEVSEButtonDescription

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSEButtonDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @override
    async def async_press(self) -> None:
        """Press the button."""
        with openevse_exception_handler(0.0):
            await self.entity_description.press_fn(self.coordinator.charger)
