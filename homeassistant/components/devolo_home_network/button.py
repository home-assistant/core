"""Platform for button integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DevoloHomeNetworkConfigEntry
from .const import DOMAIN, IDENTIFY, PAIRING, RESTART, START_WPS
from .entity import DevoloEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DevoloButtonEntityDescription(ButtonEntityDescription):
    """Describes devolo button entity."""

    press_func: Callable[[Device], Awaitable[bool]]


BUTTON_TYPES: dict[str, DevoloButtonEntityDescription] = {
    IDENTIFY: DevoloButtonEntityDescription(
        key=IDENTIFY,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=ButtonDeviceClass.IDENTIFY,
        press_func=lambda device: device.plcnet.async_identify_device_start(),  # type: ignore[union-attr]
    ),
    PAIRING: DevoloButtonEntityDescription(
        key=PAIRING,
        press_func=lambda device: device.plcnet.async_pair_device(),  # type: ignore[union-attr]
    ),
    RESTART: DevoloButtonEntityDescription(
        key=RESTART,
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_func=lambda device: device.device.async_restart(),  # type: ignore[union-attr]
    ),
    START_WPS: DevoloButtonEntityDescription(
        key=START_WPS,
        press_func=lambda device: device.device.async_start_wps(),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeNetworkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get all devices and buttons and setup them via config entry."""
    device = entry.runtime_data.device

    entities: list[DevoloButtonEntity] = []
    if device.plcnet:
        entities.append(
            DevoloButtonEntity(
                entry,
                BUTTON_TYPES[IDENTIFY],
            )
        )
        entities.append(
            DevoloButtonEntity(
                entry,
                BUTTON_TYPES[PAIRING],
            )
        )
    if device.device and "restart" in device.device.features:
        entities.append(
            DevoloButtonEntity(
                entry,
                BUTTON_TYPES[RESTART],
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloButtonEntity(
                entry,
                BUTTON_TYPES[START_WPS],
            )
        )
    async_add_entities(entities)


class DevoloButtonEntity(DevoloEntity, ButtonEntity):
    """Representation of a devolo button."""

    entity_description: DevoloButtonEntityDescription

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        description: DevoloButtonEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry)

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_func(self.device)
        except DevicePasswordProtected as ex:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="password_protected",
                translation_placeholders={"title": self.entry.title},
            ) from ex
        except DeviceUnavailable as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_response",
                translation_placeholders={"title": self.entry.title},
            ) from ex
