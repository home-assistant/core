"""Platform for switch integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import WifiGuestAccessGet
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SWITCH_GUEST_WIFI, SWITCH_LEDS
from .entity import DevoloCoordinatorEntity

_DataT = TypeVar("_DataT", bound=WifiGuestAccessGet | bool)


@dataclass(frozen=True, kw_only=True)
class DevoloSwitchEntityDescription(SwitchEntityDescription, Generic[_DataT]):
    """Describes devolo switch entity."""

    is_on_func: Callable[[_DataT], bool]
    turn_on_func: Callable[[Device], Awaitable[bool]]
    turn_off_func: Callable[[Device], Awaitable[bool]]


SWITCH_TYPES: dict[str, DevoloSwitchEntityDescription[Any]] = {
    SWITCH_GUEST_WIFI: DevoloSwitchEntityDescription[WifiGuestAccessGet](
        key=SWITCH_GUEST_WIFI,
        is_on_func=lambda data: data.enabled is True,
        turn_on_func=lambda device: device.device.async_set_wifi_guest_access(True),  # type: ignore[union-attr]
        turn_off_func=lambda device: device.device.async_set_wifi_guest_access(False),  # type: ignore[union-attr]
    ),
    SWITCH_LEDS: DevoloSwitchEntityDescription[bool](
        key=SWITCH_LEDS,
        entity_category=EntityCategory.CONFIG,
        is_on_func=bool,
        turn_on_func=lambda device: device.device.async_set_led_setting(True),  # type: ignore[union-attr]
        turn_off_func=lambda device: device.device.async_set_led_setting(False),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinators"]

    entities: list[DevoloSwitchEntity[Any]] = []
    if device.device and "led" in device.device.features:
        entities.append(
            DevoloSwitchEntity(
                entry,
                coordinators[SWITCH_LEDS],
                SWITCH_TYPES[SWITCH_LEDS],
                device,
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloSwitchEntity(
                entry,
                coordinators[SWITCH_GUEST_WIFI],
                SWITCH_TYPES[SWITCH_GUEST_WIFI],
                device,
            )
        )
    async_add_entities(entities)


class DevoloSwitchEntity(DevoloCoordinatorEntity[_DataT], SwitchEntity):
    """Representation of a devolo switch."""

    entity_description: DevoloSwitchEntityDescription[_DataT]

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[_DataT],
        description: DevoloSwitchEntityDescription[_DataT],
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator, device)

    @property
    def is_on(self) -> bool:
        """State of the switch."""
        return self.entity_description.is_on_func(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.turn_on_func(self.device)
        except DevicePasswordProtected as ex:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="password_protected",
                translation_placeholders={"title": self.entry.title},
            ) from ex
        except DeviceUnavailable:
            pass  # The coordinator will handle this
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.turn_off_func(self.device)
        except DevicePasswordProtected as ex:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="password_protected",
                translation_placeholders={"title": self.entry.title},
            ) from ex
        except DeviceUnavailable:
            pass  # The coordinator will handle this
        await self.coordinator.async_request_refresh()
