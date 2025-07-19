# homeassistant/components/wiim/button.py
"""Support for WiiM buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from wiim.consts import WiimHttpCommand
from wiim.exceptions import WiimException
from wiim.wiim_device import WiimDevice

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WiimConfigEntry
from .const import SDK_LOGGER
from .entity import WiimBaseEntity, exception_wrap


@dataclass(frozen=True, kw_only=True)
class WiimButtonEntityDescription(ButtonEntityDescription):
    """Class describing WiiM button entities."""

    press_action: Callable[[WiimDevice], Coroutine[Any, Any, None]]


BUTTON_DESCRIPTIONS: tuple[WiimButtonEntityDescription, ...] = (
    WiimButtonEntityDescription(
        key="reboot_device",
        translation_key="reboot_device",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda device: device._http_command_ok(WiimHttpCommand.REBOOT),  # noqa: SLF001
    ),
    WiimButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        icon="mdi:clock",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda device: device._http_command_ok(  # noqa: SLF001
            WiimHttpCommand.TIMESYNC,
            device._format_time_for_sync(),  # noqa: SLF001
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WiimConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiiM buttons from a config entry."""
    wiim_device: WiimDevice = entry.runtime_data

    # Check if HTTP API is available for buttons that require it
    if not wiim_device._http_api:  # noqa: SLF001
        SDK_LOGGER.info(
            "HTTP API not available for %s, skipping HTTP-based buttons.",
            wiim_device.name,
        )
        return

    entities = [
        WiimButton(wiim_device, description) for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class WiimButton(WiimBaseEntity, ButtonEntity):
    """Representation of a WiiM button."""

    entity_description: WiimButtonEntityDescription

    def __init__(
        self,
        wiim_device: WiimDevice,
        description: WiimButtonEntityDescription,
    ) -> None:
        """Initialize the WiiM button."""
        super().__init__(wiim_device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device.udn}-{self.entity_description.key}"

    @exception_wrap
    async def async_press(self) -> None:
        """Handle the button press."""
        if not self._device.available:
            SDK_LOGGER.warning(
                "Button press failed: Device %s is not available.", self._device.name
            )
            return

        # Specific check for HTTP API if the action requires it
        if self.entity_description.key in ["reboot_device", "sync_time"]:
            if not self._device._http_api:  # noqa: SLF001
                SDK_LOGGER.error(
                    "Cannot press button '%s' for %s: HTTP API is not configured or available.",
                    self.entity_description.key,
                    self._device.name,
                )
                raise WiimException(
                    f"HTTP API not available for action {self.entity_description.key}"
                )

        await self.entity_description.press_action(self._device)
