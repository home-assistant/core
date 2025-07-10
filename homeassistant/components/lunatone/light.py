"""Platform for Lunatone light integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from awesomeversion import AwesomeVersion
from lunatone_dali_api_client import Device
from lunatone_dali_api_client.models import ControlData

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LunatoneDALIIoTConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneDALIIoTConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Light platform."""
    info = config_entry.runtime_data.info
    devices = config_entry.runtime_data.devices

    interface_version = AwesomeVersion(info.version.split("/")[0][1:])

    # Add devices
    async_add_entities(
        [
            LunatoneLight(device, info.serial_number, interface_version)
            for device in devices.devices
        ],
        update_before_add=True,
    )


class LunatoneLight(LightEntity):
    """Representation of a Lunatone light."""

    unique_id: str

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = True

    def __init__(
        self, device: Device, unique_id_prefix: str, interface_version: AwesomeVersion
    ) -> None:
        """Initialize a LunatoneLight."""
        self._interface_version = interface_version
        self._device = device
        self._attr_unique_id = f"{unique_id_prefix}-device{self._device.id}"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        is_on: bool = self._device.is_on
        return is_on

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)}, name=self._device.name
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
        if self._interface_version >= "1.10.0" and self._interface_version < "1.15.0":
            await asyncio.sleep(0.02)
        await self._device.async_update()
