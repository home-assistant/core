"""Platform for button integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, START_WPS
from .entity import DevoloEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class DevoloButtonRequiredKeysMixin:
    """Mixin for required keys."""

    press_func: Callable[[Device], Awaitable[bool]]


@dataclass
class DevoloButtonEntityDescription(
    ButtonEntityDescription, DevoloButtonRequiredKeysMixin
):
    """Describes devolo button entity."""


BUTTON_TYPES: dict[str, DevoloButtonEntityDescription] = {
    START_WPS: DevoloButtonEntityDescription(
        key=START_WPS,
        icon="mdi:wifi-plus",
        name="Start WPS",
        press_func=lambda device: device.device.async_start_wps(),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and buttons and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]

    entities: list[DevoloButtonEntity] = []
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloButtonEntity(
                entry,
                BUTTON_TYPES[START_WPS],
                device,
            )
        )
    async_add_entities(entities)


class DevoloButtonEntity(DevoloEntity, ButtonEntity):
    """Representation of a devolo button."""

    def __init__(
        self,
        entry: ConfigEntry,
        description: DevoloButtonEntityDescription,
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloButtonEntityDescription = description
        super().__init__(entry, device)

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_func(self.device)
        except DevicePasswordProtected:
            self.entry.async_start_reauth(self.hass)
        except DeviceUnavailable:
            _LOGGER.error("Device %s did not respond", self.entry.title)
