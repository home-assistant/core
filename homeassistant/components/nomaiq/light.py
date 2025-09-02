"""Platform for light integration."""

from __future__ import annotations

from typing import Any

import ayla_iot_unofficial
import ayla_iot_unofficial.device

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NomaIQConfigEntry
from .const import DOMAIN
from .coordinator import NomaIQDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NomaIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Noma IQ Light platform."""
    coordinator: NomaIQDataUpdateCoordinator = entry.runtime_data

    for device in coordinator.data:
        if (
            "light_control" in device.properties_full
            and "light_name" in device.properties_full
        ):
            async_add_entities(
                [NomaIQLightEntity(coordinator, device)], update_before_add=False
            )


class NomaIQLightEntity(LightEntity):
    """Representation of a NomaIQ Light."""

    def __init__(
        self,
        coordinator: NomaIQDataUpdateCoordinator,
        device: ayla_iot_unofficial.device.Device,
    ) -> None:
        """Initialize a NomaIQ light."""
        self.coordinator = coordinator
        self._device = device
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_name = device.get_property_value("light_name") or device.name
        self._attr_unique_id = f"nomaiq_light_{device.serial_number}"
        self._attr_has_entity_name = device.get_property_value("light_name")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=device.name,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        data: list[ayla_iot_unofficial.device.Device] = self.coordinator.data
        device: ayla_iot_unofficial.device.Device | None = next(
            (d for d in data if d.serial_number == self._device.serial_number),
            None,
        )
        return device and device.get_property_value("light_control")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self._device.async_set_property_value("light_control", 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self._device.async_set_property_value("light_control", 0)

    async def async_update(self) -> None:
        """Update the light state."""
        await self.coordinator.async_request_refresh()
