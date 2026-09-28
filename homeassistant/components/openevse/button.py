"""Support for OpenEVSE button entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp import OpenEVSE

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenEVSEConfigEntry
from .entity import OpenEVSEEntity
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


class OpenEVSEButton(OpenEVSEEntity, ButtonEntity):
    """Implementation of an OpenEVSE button."""

    entity_description: OpenEVSEButtonDescription

    @override
    async def async_press(self) -> None:
        """Press the button."""
        with openevse_exception_handler():
            await self.entity_description.press_fn(self.coordinator.charger)
