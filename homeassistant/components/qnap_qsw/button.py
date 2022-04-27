"""Support for the QNAP QSW buttons."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aioqsw.const import QSD_PRODUCT, QSD_SYSTEM_BOARD

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import QswEntity
from .const import DOMAIN, QSW_REBOOT
from .coordinator import QswUpdateCoordinator


@dataclass
class QswButtonEntityDescription(ButtonEntityDescription):
    """A class that describes QNAP QSW button entities."""

    press_action: Callable | None = None


BUTTON_TYPES: Final[tuple[QswButtonEntityDescription, ...]] = (
    QswButtonEntityDescription(
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        key=QSW_REBOOT,
        name="Reboot",
        press_action=lambda qsw: qsw.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW buttons from a config_entry."""
    coordinator: QswUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        QswButton(coordinator, description, entry) for description in BUTTON_TYPES
    )


class QswButton(QswEntity, ButtonEntity):
    """Define a QNAP QSW button."""

    entity_description: QswButtonEntityDescription

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        description: QswButtonEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = (
            f"{self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT)} {description.name}"
        )
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the QNAP QSW button action."""
        if self.entity_description.press_action:
            await self.entity_description.press_action(self.coordinator.qsw)
