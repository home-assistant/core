"""Buttons for Hunter Douglas Powerview advanced features."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiopvapi.resources.shade import BaseShade, factory as PvShade

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ROOM_ID_IN_SHADE, ROOM_NAME_UNICODE
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData


@dataclass(frozen=True)
class PowerviewButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable[[BaseShade], Any]


@dataclass(frozen=True)
class PowerviewButtonDescription(
    ButtonEntityDescription, PowerviewButtonDescriptionMixin
):
    """Class to describe a Button entity."""


BUTTONS: Final = [
    PowerviewButtonDescription(
        key="calibrate",
        translation_key="calibrate",
        icon="mdi:swap-vertical-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda shade: shade.calibrate(),
    ),
    PowerviewButtonDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda shade: shade.jog(),
    ),
    PowerviewButtonDescription(
        key="favorite",
        translation_key="favorite",
        icon="mdi:heart",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda shade: shade.favorite(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the hunter douglas advanced feature buttons."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []
    for raw_shade in pv_entry.shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")

        for description in BUTTONS:
            entities.append(
                PowerviewButton(
                    pv_entry.coordinator,
                    pv_entry.device_info,
                    room_name,
                    shade,
                    name_before_refresh,
                    description,
                )
            )

    async_add_entities(entities)


class PowerviewButton(ShadeEntity, ButtonEntity):
    """Representation of an advanced feature button."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
        description: PowerviewButtonDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self.entity_description: PowerviewButtonDescription = description
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_action(self._shade)
