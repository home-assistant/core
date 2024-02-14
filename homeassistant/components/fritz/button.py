"""Switches for AVM Fritz!Box buttons."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import AvmWrapper
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FritzButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable


@dataclass(frozen=True)
class FritzButtonDescription(ButtonEntityDescription, FritzButtonDescriptionMixin):
    """Class to describe a Button entity."""


BUTTONS: Final = [
    FritzButtonDescription(
        key="firmware_update",
        translation_key="firmware_update",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_firmware_update(),
    ),
    FritzButtonDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_reboot(),
    ),
    FritzButtonDescription(
        key="reconnect",
        translation_key="reconnect",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_reconnect(),
    ),
    FritzButtonDescription(
        key="cleanup",
        translation_key="cleanup",
        icon="mdi:broom",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda avm_wrapper: avm_wrapper.async_trigger_cleanup(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    _LOGGER.debug("Setting up buttons")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [FritzButton(avm_wrapper, entry.title, button) for button in BUTTONS]
    )


class FritzButton(ButtonEntity):
    """Defines a Fritz!Box base button."""

    entity_description: FritzButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        description: FritzButtonDescription,
    ) -> None:
        """Initialize Fritz!Box button."""
        self.entity_description = description
        self.avm_wrapper = avm_wrapper

        self._attr_unique_id = f"{self.avm_wrapper.unique_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, avm_wrapper.mac)},
            name=device_friendly_name,
        )

    async def async_press(self) -> None:
        """Triggers Fritz!Box service."""
        await self.entity_description.press_action(self.avm_wrapper)
