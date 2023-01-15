"""iNELS cover entity."""
from __future__ import annotations

from typing import Any

from inelsmqtt.const import RFJA_12, SHUTTER_STATE_LIST, STOP_DOWN, STOP_UP
from inelsmqtt.devices import Device

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import DEVICES, DOMAIN, ICON_SHUTTER_CLOSED, ICON_SHUTTER_OPEN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS cover from config entry."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    async_add_entities(
        [
            InelsCover(device)
            for device in device_list
            if device.device_type == Platform.COVER
        ],
    )


class InelsCover(InelsBaseEntity, CoverEntity):
    """Cover class for Home assistant."""

    def __init__(self, device: Device) -> None:
        """Initialize a cover."""
        super().__init__(device=device)

        if self._device.inels_type is RFJA_12:
            self._attr_device_class = CoverDeviceClass.SHUTTER
        else:
            self._attr_device_class = CoverDeviceClass.SHUTTER

    @property
    def icon(self) -> str | None:
        """Cover icon."""
        return ICON_SHUTTER_CLOSED if self.is_closed is True else ICON_SHUTTER_OPEN

    @property
    def is_closed(self) -> bool | None:
        """Cover is closed."""
        dev = self._device
        state = dev.state if dev.state in SHUTTER_STATE_LIST else dev.values.ha_value

        return state is STATE_CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.hass.async_add_executor_job(self._device.set_ha_value, STATE_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.hass.async_add_executor_job(self._device.set_ha_value, STATE_CLOSED)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        await self.hass.async_add_executor_job(
            self._device.set_ha_value,
            STOP_UP if self.is_closed is False else STOP_DOWN,
        )
