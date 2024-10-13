"""Support for Elgato button."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from elgato import Elgato, ElgatoError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElgatorConfigEntry
from .coordinator import ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity


@dataclass(frozen=True, kw_only=True)
class ElgatoButtonEntityDescription(ButtonEntityDescription):
    """Class describing Elgato button entities."""

    press_fn: Callable[[Elgato], Awaitable[Any]]


BUTTONS = [
    ElgatoButtonEntityDescription(
        key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.identify(),
    ),
    ElgatoButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.restart(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elgato button based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ElgatoButtonEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in BUTTONS
    )


class ElgatoButtonEntity(ElgatoEntity, ButtonEntity):
    """Defines an Elgato button."""

    entity_description: ElgatoButtonEntityDescription

    def __init__(
        self,
        coordinator: ElgatoDataUpdateCoordinator,
        description: ElgatoButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.info.serial_number}_{description.key}"
        )

    async def async_press(self) -> None:
        """Trigger button press on the Elgato device."""
        try:
            await self.entity_description.press_fn(self.coordinator.client)
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while communicating with the Elgato Light"
            ) from error
