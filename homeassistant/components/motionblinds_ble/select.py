"""Sensor entities for the Motionblinds BLE integration."""

from __future__ import annotations

import logging

from motionblindsble.const import MotionBlindType, MotionSpeedLevel
from motionblindsble.device import MotionDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_SPEED,
    CONF_BLIND_TYPE,
    CONF_MAC_CODE,
    DOMAIN,
    ICON_SPEED,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


SELECT_TYPES: dict[str, SelectEntityDescription] = {
    ATTR_SPEED: SelectEntityDescription(
        key=ATTR_SPEED,
        translation_key=ATTR_SPEED,
        icon=ICON_SPEED,
        entity_category=EntityCategory.CONFIG,
        options=[str(speed_level.value) for speed_level in MotionSpeedLevel],
        has_entity_name=True,
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up speed select entities based on a config entry."""

    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]

    if device.blind_type not in [MotionBlindType.CURTAIN, MotionBlindType.VERTICAL]:
        async_add_entities([SpeedSelect(device, entry)])


class SpeedSelect(SelectEntity):
    """Representation of a speed select entity."""

    _device: MotionDevice
    entity_description: SelectEntityDescription

    def __init__(self, device: MotionDevice, entry: ConfigEntry) -> None:
        """Initialize the speed select entity."""
        _LOGGER.info(
            "(%s) Setting up speed select entity",
            entry.data[CONF_MAC_CODE],
        )
        self._device = device
        self._device.register_speed_callback(self.async_update_speed)
        self.entity_description = SELECT_TYPES[ATTR_SPEED]

        self._attr_unique_id: str = f"{entry.data[CONF_ADDRESS]}_{ATTR_SPEED}"
        self._attr_device_info: DeviceInfo = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=entry.data[CONF_BLIND_TYPE],
            name=device.display_name,
        )
        self._attr_current_option: str | None = None

    @callback
    def async_update_speed(self, speed_level: MotionSpeedLevel | None) -> None:
        """Update the speed level."""
        self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected speed_level."""
        speed_level = MotionSpeedLevel(int(option))
        await self._device.speed(speed_level)
        self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()
