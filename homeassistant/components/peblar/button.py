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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PeblarConfigEntry, PeblarUserConfigurationDataUpdateCoordinator


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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar buttons based on a config entry."""
    async_add_entities(
        PeblarButtonEntity(
            entry=entry,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarButtonEntity(
    CoordinatorEntity[PeblarUserConfigurationDataUpdateCoordinator], ButtonEntity
):
    """Defines an Peblar button."""

    entity_description: PeblarButtonEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=entry.runtime_data.user_configuraton_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )

    async def async_press(self) -> None:
        """Trigger button press on the Peblar device."""
        await self.entity_description.press_fn(self.coordinator.peblar)
