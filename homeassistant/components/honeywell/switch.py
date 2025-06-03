"""Support for Honeywell switches."""

from __future__ import annotations

from typing import Any

from aiosomecomfort import SomeComfortError
from aiosomecomfort.device import Device as SomeComfortDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HoneywellConfigEntry, HoneywellData
from .const import DOMAIN

EMERGENCY_HEAT_KEY = "emergency_heat"

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key=EMERGENCY_HEAT_KEY,
        translation_key=EMERGENCY_HEAT_KEY,
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HoneywellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Honeywell switches."""
    data = config_entry.runtime_data
    async_add_entities(
        HoneywellSwitch(data, device, description)
        for device in data.devices.values()
        if device.raw_ui_data.get("SwitchEmergencyHeatAllowed")
        for description in SWITCH_TYPES
    )


class HoneywellSwitch(SwitchEntity):
    """Representation of a honeywell switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        honeywell_data: HoneywellData,
        device: SomeComfortDevice,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        self._data = honeywell_data
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.deviceid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.deviceid)},
            name=device.name,
            manufacturer="Honeywell",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on if heat mode is enabled."""
        try:
            await self._device.set_system_mode("emheat")
        except SomeComfortError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="switch_failed_on"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off if on."""
        if self.is_on:
            try:
                await self._device.set_system_mode("off")

            except SomeComfortError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="switch_failed_off"
                ) from err

    @property
    def is_on(self) -> bool:
        """Return true if Emergency heat is enabled."""
        return self._device.system_mode == "emheat"
