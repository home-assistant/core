"""Platform for Lunatone light integration."""

from __future__ import annotations

from typing import Any

from lunatone_dali_api_client import Device
from lunatone_dali_api_client.models import ControlData

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LunatoneDALIIoTConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneDALIIoTConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Light platform."""
    info = config_entry.runtime_data.info
    devices = config_entry.runtime_data.devices

    # Add devices
    async_add_entities(
        [LunatoneLight(device, info.data.device.serial) for device in devices.devices],
        update_before_add=True,
    )


class LunatoneLight(LightEntity):
    """Representation of a Lunatone Light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, device: Device, unique_id_prefix: str) -> None:
        """Initialize a LunatoneLight."""
        self._device = device
        self._attr_unique_id = f"{unique_id_prefix}-device{self._device.data.id}"

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._device.data.name

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._device.data.features.switchable.status

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        if self.unique_id is None:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Lunatone",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self._device.async_control(ControlData(switchable=True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._device.async_control(ControlData(switchable=False))

    async def async_update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        await self._device.async_update()
