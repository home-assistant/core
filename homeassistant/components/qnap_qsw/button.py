"""Support for the QNAP QSW buttons."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from aioqsw.localapi import QnapQswApi

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, QSW_REBOOT
from .coordinator import QswUpdateCoordinator
from .entity import QswEntity


@dataclass
class QswButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable[[QnapQswApi], Awaitable[bool]]


@dataclass
class QswButtonDescription(ButtonEntityDescription, QswButtonDescriptionMixin):
    """Class to describe a Button entity."""


BUTTON_TYPES: Final[tuple[QswButtonDescription, ...]] = (
    QswButtonDescription(
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

    entity_description: QswButtonDescription

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        description: QswButtonDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.product} {description.name}"
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the QNAP QSW button action."""
        await self.entity_description.press_action(self.coordinator.qsw)
