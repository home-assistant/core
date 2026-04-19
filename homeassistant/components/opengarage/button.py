"""OpenGarage button."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from opengarage import OpenGarage

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
from .entity import OpenGarageEntity


@dataclass(frozen=True, kw_only=True)
class OpenGarageButtonEntityDescription(ButtonEntityDescription):
    """OpenGarage Browser button description."""

    press_action: Callable[[OpenGarage], Any]


BUTTONS: tuple[OpenGarageButtonEntityDescription, ...] = (
    OpenGarageButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda opengarage: opengarage.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenGarage button entities."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        OpenGarageButtonEntity(
            coordinator, cast(str, config_entry.unique_id), description
        )
        for description in BUTTONS
    )


class OpenGarageButtonEntity(OpenGarageEntity, ButtonEntity):
    """Representation of an OpenGarage button."""

    entity_description: OpenGarageButtonEntityDescription

    def __init__(
        self,
        coordinator: OpenGarageDataUpdateCoordinator,
        device_id: str,
        description: OpenGarageButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id, description)

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_action(
            self.coordinator.open_garage_connection
        )
        await self.coordinator.async_refresh()
