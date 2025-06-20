"""Support for Peblar button."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from peblar import Peblar

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PeblarConfigEntry, PeblarUserConfigurationDataUpdateCoordinator
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarButtonEntityDescription(ButtonEntityDescription):
    """Describe a Peblar button."""

    press_fn: Callable[[Peblar], Awaitable[Any]]


DESCRIPTIONS = [
    PeblarButtonEntityDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=lambda x: x.identify(),
    ),
    PeblarButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=lambda x: x.reboot(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar buttons based on a config entry."""
    async_add_entities(
        PeblarButtonEntity(
            entry=entry,
            coordinator=entry.runtime_data.user_configuration_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarButtonEntity(
    PeblarEntity[PeblarUserConfigurationDataUpdateCoordinator],
    ButtonEntity,
):
    """Defines an Peblar button."""

    entity_description: PeblarButtonEntityDescription

    @peblar_exception_handler
    async def async_press(self) -> None:
        """Trigger button press on the Peblar device."""
        await self.entity_description.press_fn(self.coordinator.peblar)
