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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QSW_REBOOT
from .coordinator import QnapQswConfigEntry, QswDataCoordinator
from .entity import QswDataEntity


@dataclass(frozen=True, kw_only=True)
class QswButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: Callable[[QnapQswApi], Awaitable[bool]]


BUTTON_TYPES: Final[tuple[QswButtonDescription, ...]] = (
    QswButtonDescription(
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        key=QSW_REBOOT,
        press_action=lambda qsw: qsw.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QnapQswConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add QNAP QSW buttons from a config_entry."""
    coordinator = entry.runtime_data.data_coordinator
    async_add_entities(
        QswButton(coordinator, description, entry) for description in BUTTON_TYPES
    )


class QswButton(QswDataEntity, ButtonEntity):
    """Define a QNAP QSW button."""

    _attr_has_entity_name = True

    entity_description: QswButtonDescription

    def __init__(
        self,
        coordinator: QswDataCoordinator,
        description: QswButtonDescription,
        entry: QnapQswConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the QNAP QSW button action."""
        await self.entity_description.press_action(self.coordinator.qsw)
