"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .router import FreeboxRouter


@dataclass
class FreeboxButtonRequiredKeysMixin:
    """Mixin for required keys."""

    async_press: Callable[[FreeboxRouter], Awaitable]


@dataclass
class FreeboxButtonEntityDescription(
    ButtonEntityDescription, FreeboxButtonRequiredKeysMixin
):
    """Class describing Freebox button entities."""


BUTTON_DESCRIPTIONS: tuple[FreeboxButtonEntityDescription, ...] = (
    FreeboxButtonEntityDescription(
        key="reboot",
        name="Reboot Freebox",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        async_press=lambda router: router.reboot(),
    ),
    FreeboxButtonEntityDescription(
        key="mark_calls_as_read",
        name="Mark calls as read",
        entity_category=EntityCategory.DIAGNOSTIC,
        async_press=lambda router: router.call.mark_calls_log_as_read(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buttons."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    entities = [
        FreeboxButton(router, description) for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities, True)


class FreeboxButton(ButtonEntity):
    """Representation of a Freebox button."""

    entity_description: FreeboxButtonEntityDescription

    def __init__(
        self, router: FreeboxRouter, description: FreeboxButtonEntityDescription
    ) -> None:
        """Initialize a Freebox button."""
        self.entity_description = description
        self._router = router
        self._attr_unique_id = f"{router.mac} {description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.async_press(self._router)
