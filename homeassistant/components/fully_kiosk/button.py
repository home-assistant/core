"""Fully Kiosk Browser button."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fullykiosk import FullyKiosk

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FullyKioskConfigEntry
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


@dataclass(frozen=True, kw_only=True)
class FullyButtonEntityDescription(ButtonEntityDescription):
    """Fully Kiosk Browser button description."""

    press_action: Callable[[FullyKiosk], Any]


BUTTONS: tuple[FullyButtonEntityDescription, ...] = (
    FullyButtonEntityDescription(
        key="restartApp",
        translation_key="restart_browser",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda fully: fully.restartApp(),
    ),
    FullyButtonEntityDescription(
        key="rebootDevice",
        translation_key="restart_device",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda fully: fully.rebootDevice(),
    ),
    FullyButtonEntityDescription(
        key="toForeground",
        translation_key="to_foreground",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda fully: fully.toForeground(),
    ),
    FullyButtonEntityDescription(
        key="toBackground",
        translation_key="to_background",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda fully: fully.toBackground(),
    ),
    FullyButtonEntityDescription(
        key="loadStartUrl",
        translation_key="load_start_url",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda fully: fully.loadStartUrl(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FullyKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser button entities."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        FullyButtonEntity(coordinator, description) for description in BUTTONS
    )


class FullyButtonEntity(FullyKioskEntity, ButtonEntity):
    """Representation of a Fully Kiosk Browser button."""

    entity_description: FullyButtonEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: FullyButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"

    async def async_press(self) -> None:
        """Set the value of the entity."""
        await self.entity_description.press_action(self.coordinator.fully)
        await self.coordinator.async_refresh()
