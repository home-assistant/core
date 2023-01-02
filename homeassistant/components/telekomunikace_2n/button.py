"""2N Telekomunikace button platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from py2n import Py2NDevice

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Py2NDeviceCoordinator, Py2NDeviceEntity
from .const import DOMAIN


@dataclass
class Py2NDeviceButtonRequiredKeysMixin:
    """Class for 2N Telekomunikace entity required keys."""

    press_action: Callable[[Py2NDevice], Any]


@dataclass
class Py2NDeviceButtonEntityDescription(
    ButtonEntityDescription, Py2NDeviceButtonRequiredKeysMixin
):
    """A class that describes button entities."""


BUTTON_TYPES: tuple[Py2NDeviceButtonEntityDescription, ...] = (
    Py2NDeviceButtonEntityDescription(
        key="restart",
        name="Restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda device: device.restart(),
    ),
    Py2NDeviceButtonEntityDescription(
        key="audio_test",
        name="Audio Test",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda device: device.audio_test(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator: Py2NDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]

    buttons = []
    for description in BUTTON_TYPES:
        buttons.append(Py2NDeviceButton(coordinator, description, coordinator.device))
    async_add_entities(buttons, False)


class Py2NDeviceButton(Py2NDeviceEntity, ButtonEntity):
    """Define a 2N Telekomunikace button."""

    entity_description: Py2NDeviceButtonEntityDescription

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: Py2NDeviceButtonEntityDescription,
        device: Py2NDevice,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description, device)

    async def async_press(self) -> None:
        """Handle button press."""
        await self.safe_request(
            lambda: self.entity_description.press_action(self.device)
        )
