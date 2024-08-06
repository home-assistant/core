"""Buttons for Hunter Douglas Powerview advanced features."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiopvapi.helpers.constants import (
    ATTR_NAME,
    MOTION_CALIBRATE,
    MOTION_FAVORITE,
    MOTION_JOG,
)
from aiopvapi.hub import Hub
from aiopvapi.resources.shade import BaseShade

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo


@dataclass(frozen=True)
class PowerviewButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable[[BaseShade | Hub], Any]
    create_entity_fn: Callable[[BaseShade | Hub], bool]


@dataclass(frozen=True)
class PowerviewButtonDescription(
    ButtonEntityDescription, PowerviewButtonDescriptionMixin
):
    """Class to describe a Button entity."""


BUTTONS_SHADE: Final = [
    PowerviewButtonDescription(
        key="calibrate",
        translation_key="calibrate",
        icon="mdi:swap-vertical-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        create_entity_fn=lambda shade: shade.is_supported(MOTION_CALIBRATE),
        press_action=lambda shade: shade.calibrate(),
    ),
    PowerviewButtonDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.DIAGNOSTIC,
        create_entity_fn=lambda shade: shade.is_supported(MOTION_JOG),
        press_action=lambda shade: shade.jog(),
    ),
    PowerviewButtonDescription(
        key="favorite",
        translation_key="favorite",
        icon="mdi:heart",
        entity_category=EntityCategory.DIAGNOSTIC,
        create_entity_fn=lambda shade: shade.is_supported(MOTION_FAVORITE),
        press_action=lambda shade: shade.favorite(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the hunter douglas advanced feature buttons."""
    pv_entry = entry.runtime_data
    entities: list[ButtonEntity] = []
    for shade in pv_entry.shade_data.values():
        room_name = getattr(pv_entry.room_data.get(shade.room_id), ATTR_NAME, "")
        entities.extend(
            PowerviewShadeButton(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                shade,
                shade.name,
                description,
            )
            for description in BUTTONS_SHADE
            if description.create_entity_fn(shade)
        )
    async_add_entities(entities)


class PowerviewShadeButton(ShadeEntity, ButtonEntity):
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
        async with self.coordinator.radio_operation_lock:
            await self.entity_description.press_action(self._shade)
