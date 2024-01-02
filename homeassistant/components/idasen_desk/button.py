"""Representation of Idasen Desk buttons."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeskData, IdasenDeskCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdasenDeskButtonDescriptionMixin:
    """Mixin to describe a IdasenDesk button entity."""

    press_action: Callable[
        [IdasenDeskCoordinator], Callable[[], Coroutine[Any, Any, Any]]
    ]


@dataclass(frozen=True)
class IdasenDeskButtonDescription(
    ButtonEntityDescription, IdasenDeskButtonDescriptionMixin
):
    """Class to describe a IdasenDesk button entity."""


BUTTONS: Final = [
    IdasenDeskButtonDescription(
        key="connect",
        name="Connect",
        icon="mdi:bluetooth-connect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.async_connect,
    ),
    IdasenDeskButtonDescription(
        key="disconnect",
        name="Disconnect",
        icon="mdi:bluetooth-off",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.async_disconnect,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IdasenDeskButton(data.address, data.device_info, data.coordinator, button)
        for button in BUTTONS
    )


class IdasenDeskButton(ButtonEntity):
    """Defines a IdasenDesk button."""

    entity_description: IdasenDeskButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        address: str,
        device_info: DeviceInfo,
        coordinator: IdasenDeskCoordinator,
        description: IdasenDeskButtonDescription,
    ) -> None:
        """Initialize the IdasenDesk button entity."""
        self.entity_description = description

        self._attr_unique_id = f"{self.entity_description.key}-{address}"
        self._attr_device_info = device_info
        self._address = address
        self._coordinator = coordinator

    async def async_press(self) -> None:
        """Triggers the IdasenDesk button press service."""
        _LOGGER.debug(
            "Trigger %s for %s",
            self.entity_description.key,
            self._address,
        )
        await self.entity_description.press_action(self._coordinator)()
