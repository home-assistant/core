"""Platform for Lunatone light integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from awesomeversion import AwesomeVersion
from lunatone_rest_api_client import Device

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Light platform."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_devices = config_entry.runtime_data.coordinator_devices

    info_api = coordinator_info.info_api
    devices_api = coordinator_devices.devices_api

    interface_version = AwesomeVersion(info_api.version.split("/")[0][1:])

    # Add devices
    async_add_entities(
        [
            LunatoneLight(device, info_api.serial_number, interface_version)
            for device in devices_api.devices
        ],
        update_before_add=True,
    )


class LunatoneLight(LightEntity):
    """Representation of a Lunatone light."""

    unique_id: str

    _unavailable_logged: bool = False

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = True

    def __init__(
        self,
        device_api: Device,
        interface_serial_number: int,
        interface_version: AwesomeVersion,
    ) -> None:
        """Initialize a LunatoneLight."""
        self._interface_version = interface_version
        self._interface_serial_number = interface_serial_number
        self._device_api = device_api
        self._attr_unique_id = f"{interface_serial_number}-device{self._device_api.id}"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self._device_api.is_on)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self._device_api.name,
            via_device=(DOMAIN, str(self._interface_serial_number)),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self._device_api.switch_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._device_api.switch_off()

    async def async_update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        if self._interface_version < "1.15.0":
            await asyncio.sleep(0.02)
        try:
            await self._device_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            self._attr_available = False
            if not self._unavailable_logged:
                _LOGGER.info("Light %s is unavailable: %s", self.entity_id, ex)
                self._unavailable_logged = True
        else:
            self._attr_available = True
            if self._unavailable_logged:
                _LOGGER.info("Light %s is back online", self.entity_id)
                self._unavailable_logged = False
