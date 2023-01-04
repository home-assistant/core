"""2N Telekomunikace button platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

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

from .const import DOMAIN
from .coordinator import Py2NDeviceCoordinator
from .entity import Py2NDeviceEntity


@dataclass
class Py2NDeviceButtonRequiredKeysMixin:
    """Class for 2N Telekomunikace entity required keys."""

    press_action: Callable[[Py2NDevice], Coroutine[Any, Any, None]]


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
        press_action=lambda device: cast(Coroutine[Any, Any, None], device.restart()),
    ),
    Py2NDeviceButtonEntityDescription(
        key="audio_test",
        name="Audio test",
        icon="mdi:speaker",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda device: cast(
            Coroutine[Any, Any, None], device.audio_test()
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator: Py2NDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        Py2NDeviceButton(coordinator, description, coordinator.device)
        for description in BUTTON_TYPES
    )


class Py2NDeviceButton(Py2NDeviceEntity, ButtonEntity):
    """Define a 2N Telekomunikace button."""

    entity_description: Py2NDeviceButtonEntityDescription

    async def async_press(self) -> None:
        """Handle button press."""
        await self.entity_description.press_action(self.device)
