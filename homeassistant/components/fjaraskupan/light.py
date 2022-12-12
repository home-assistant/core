"""Support for lights."""
from __future__ import annotations

from typing import Any

from fjaraskupan import COMMAND_LIGHT_ON_OFF

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Coordinator, async_setup_entry_platform


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""

    def _constructor(coordinator: Coordinator) -> list[Entity]:
        return [Light(coordinator, coordinator.device_info)]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class Light(CoordinatorEntity[Coordinator], LightEntity):
    """Light device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Coordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Init light entity."""
        super().__init__(coordinator)
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_unique_id = coordinator.device.address
        self._attr_device_info = device_info

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        async with self.coordinator.async_connect_and_update() as device:
            if ATTR_BRIGHTNESS in kwargs:
                await device.send_dim(int(kwargs[ATTR_BRIGHTNESS] * (100.0 / 255.0)))
            else:
                if not self.is_on:
                    await device.send_command(COMMAND_LIGHT_ON_OFF)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if self.is_on:
            async with self.coordinator.async_connect_and_update() as device:
                await device.send_command(COMMAND_LIGHT_ON_OFF)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if data := self.coordinator.data:
            return data.light_on
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if data := self.coordinator.data:
            return int(data.dim_level * (255.0 / 100.0))
        return None
