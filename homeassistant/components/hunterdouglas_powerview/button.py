"""Support for Powerview advanced features."""
from __future__ import annotations

import logging
from typing import Any

from aiopvapi.resources.shade import BaseShade, factory as PvShade

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DOMAIN,
    PV_API,
    PV_ROOM_DATA,
    PV_SHADE_DATA,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas advanced feature buttons."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data: dict[str | int, Any] = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator: PowerviewShadeUpdateCoordinator = pv_data[COORDINATOR]
    device_info: dict[str, Any] = pv_data[DEVICE_INFO]

    entities: list[ButtonEntity] = []
    for raw_shade in shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_request)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")

        entities.append(
            ButtonCalibrate(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
        entities.append(
            ButtonIdentify(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
        entities.append(
            ButtonUpdate(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
    async_add_entities(entities)


class ButtonCalibrate(ShadeEntity, ButtonEntity):
    """Representation of an advanced feature button."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_icon = "mdi:swap-vertical-circle-outline"

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the button entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_name = f"{self._shade_name} Calibrate"
        self._attr_unique_id = f"{self._attr_unique_id}_calibrate"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Calibrate requested for %s", self._shade_name)
        await self._shade.calibrate()


class ButtonIdentify(ShadeEntity, ButtonEntity):
    """Representation of an advanced feature button."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_icon = "mdi:crosshairs-question"
    entity_registry_enabled_default = True

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the button entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_name = f"{self._shade_name} Identify"
        self._attr_unique_id = f"{self._attr_unique_id}_identify"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Identify requested for %s", self._shade_name)
        await self._shade.jog()


class ButtonUpdate(ShadeEntity, ButtonEntity):
    """Representation of an advanced feature button."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_icon = "mdi:autorenew"
    entity_registry_enabled_default = True

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the button entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_name = f"{self._shade_name} Force Update"
        self._attr_unique_id = f"{self._attr_unique_id}_update"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Manual update of shade data run for %s", self._shade_name)
        await self._shade.refresh()
        self.data.update_shade_positions(self._shade.raw_data)
        self.async_write_ha_state()
