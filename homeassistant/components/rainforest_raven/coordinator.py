"""Data update coordination for Rainforest RAVEn devices."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
import logging
from typing import Any

from aioraven.data import DeviceInfo as RAVEnDeviceInfo
from aioraven.device import RAVEnConnectionError
from aioraven.serial import RAVEnSerialDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type RAVEnConfigEntry = ConfigEntry[RAVEnDataCoordinator]

_LOGGER = logging.getLogger(__name__)


async def _get_meter_data(
    device: RAVEnSerialDevice, meter: bytes
) -> dict[str, dict[str, Any]]:
    data = {}

    sum_info = await device.get_current_summation_delivered(meter=meter)
    demand_info = await device.get_instantaneous_demand(meter=meter)
    price_info = await device.get_current_price(meter=meter)

    if sum_info and sum_info.meter_mac_id == meter:
        data["CurrentSummationDelivered"] = asdict(sum_info)

    if demand_info and demand_info.meter_mac_id == meter:
        data["InstantaneousDemand"] = asdict(demand_info)

    if price_info and price_info.meter_mac_id == meter:
        data["PriceCluster"] = asdict(price_info)

    return data


async def _get_all_data(
    device: RAVEnSerialDevice, meter_macs: list[str]
) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {"Meters": {}}

    for meter_mac in meter_macs:
        data["Meters"][meter_mac] = await _get_meter_data(
            device, bytes.fromhex(meter_mac)
        )

    network_info = await device.get_network_info()

    if network_info and network_info.link_strength:
        data["NetworkInfo"] = asdict(network_info)

    return data


class RAVEnDataCoordinator(DataUpdateCoordinator):
    """Communication coordinator for a Rainforest RAVEn device."""

    _raven_device: RAVEnSerialDevice | None = None
    _device_info: RAVEnDeviceInfo | None = None
    config_entry: RAVEnConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RAVEnConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @property
    def device_mac_address(self) -> str | None:
        """Return the MAC address of the device."""
        if self._device_info and self._device_info.device_mac_id:
            return self._device_info.device_mac_id.hex()
        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        if (device_info := self._device_info) and (
            mac_address := self.device_mac_address
        ):
            return DeviceInfo(
                identifiers={(DOMAIN, mac_address)},
                manufacturer=device_info.manufacturer,
                model=device_info.model_id,
                model_id=device_info.model_id,
                name="RAVEn Device",
                sw_version=device_info.fw_version,
                hw_version=device_info.hw_version,
            )
        return None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self._cleanup_device()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device = await self._get_device()
            async with asyncio.timeout(5):
                return await _get_all_data(device, self.config_entry.data[CONF_MAC])
        except RAVEnConnectionError as err:
            await self._cleanup_device()
            raise UpdateFailed(f"RAVEnConnectionError: {err}") from err
        except TimeoutError:
            await self._cleanup_device()
            raise

    async def _cleanup_device(self) -> None:
        device, self._raven_device = self._raven_device, None
        if device is not None:
            await device.close()

    async def _get_device(self) -> RAVEnSerialDevice:
        if self._raven_device is not None:
            return self._raven_device

        device = RAVEnSerialDevice(self.config_entry.data[CONF_DEVICE])

        try:
            async with asyncio.timeout(5):
                await device.open()
                await device.synchronize()
                self._device_info = await device.get_device_info()
        except:
            await device.abort()
            raise

        self._raven_device = device
        return device
