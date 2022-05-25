"""Platform for switch integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SWITCH_GUEST_WIFI, SWITCH_LEDS
from .entity import DevoloEntity


@dataclass
class DevoloSwitchRequiredKeysMixin:
    """Mixin for required keys."""

    is_on_func: Callable[[dict[str, Any]], bool]
    turn_on_func: Callable[[Device], Awaitable[bool]]
    turn_off_func: Callable[[Device], Awaitable[bool]]


@dataclass
class DevoloSwitchEntityDescription(
    SwitchEntityDescription, DevoloSwitchRequiredKeysMixin
):
    """Describes devolo switch entity."""


SWITCH_TYPES: dict[str, DevoloSwitchEntityDescription] = {
    SWITCH_GUEST_WIFI: DevoloSwitchEntityDescription(
        key=SWITCH_GUEST_WIFI,
        entity_registry_enabled_default=True,
        icon="mdi:wifi",
        name="Enable guest Wifi",
        is_on_func=lambda data: data["enabled"] is True,
        turn_on_func=lambda device: device.device.async_set_wifi_guest_access(True),  # type: ignore[union-attr]
        turn_off_func=lambda device: device.device.async_set_wifi_guest_access(False),  # type: ignore[union-attr]
    ),
    SWITCH_LEDS: DevoloSwitchEntityDescription(
        key=SWITCH_LEDS,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        icon="mdi:led-off",
        name="Enable LEDs",
        is_on_func=lambda data: data["state"] == "LED_ON",  # type: ignore[no-any-return]
        turn_on_func=lambda device: device.device.async_set_led_setting(True),  # type: ignore[union-attr]
        turn_off_func=lambda device: device.device.async_set_led_setting(False),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "coordinators"
    ]

    entities: list[DevoloSwitchEntity] = []
    if device.device and "led" in device.device.features:
        entities.append(
            DevoloSwitchEntity(
                coordinators[SWITCH_LEDS],
                SWITCH_TYPES[SWITCH_LEDS],
                device,
                entry.title,
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloSwitchEntity(
                coordinators[SWITCH_GUEST_WIFI],
                SWITCH_TYPES[SWITCH_GUEST_WIFI],
                device,
                entry.title,
            )
        )
    async_add_entities(entities)


class DevoloSwitchEntity(DevoloEntity, SwitchEntity):
    """Representation of a devolo switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: DevoloSwitchEntityDescription,
        device: Device,
        device_name: str,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloSwitchEntityDescription = description
        super().__init__(coordinator, device, device_name)

    @property
    def is_on(self) -> bool:
        """State of the switch."""
        return self.entity_description.is_on_func(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        with suppress(DeviceUnavailable):
            try:
                await self.entity_description.turn_on_func(self.device)
            except DevicePasswordProtected as err:
                raise ConfigEntryAuthFailed(err) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        with suppress(DeviceUnavailable):
            try:
                await self.entity_description.turn_off_func(self.device)
            except DevicePasswordProtected as err:
                raise ConfigEntryAuthFailed(err) from err
        await self.coordinator.async_request_refresh()
