"""Mock of a devolo Home Network device."""

from __future__ import annotations

from unittest.mock import AsyncMock

from devolo_plc_api.device import Device
from devolo_plc_api.device_api.deviceapi import DeviceApi
from devolo_plc_api.plcnet_api.plcnetapi import PlcNetApi
import httpx
from zeroconf import Zeroconf
from zeroconf.asyncio import AsyncZeroconf

from .const import (
    CONNECTED_STATIONS,
    DISCOVERY_INFO,
    FIRMWARE_UPDATE_AVAILABLE,
    GUEST_WIFI,
    IP,
    NEIGHBOR_ACCESS_POINTS,
    PLCNET,
    UPTIME,
)


class MockDevice(Device):
    """Mock of a devolo Home Network device."""

    def __init__(
        self,
        ip: str,
        zeroconf_instance: AsyncZeroconf | Zeroconf | None = None,
    ) -> None:
        """Bring mock in a well defined state."""
        super().__init__(ip, zeroconf_instance)
        self._firmware_version = DISCOVERY_INFO.properties["FirmwareVersion"]
        self.reset()

    @property
    def firmware_version(self) -> str:
        """Mock firmware version currently installed."""
        return self._firmware_version

    @firmware_version.setter
    def firmware_version(self, version: str) -> None:
        """Mock firmware version currently installed."""
        self._firmware_version = version

    async def async_connect(
        self, session_instance: httpx.AsyncClient | None = None
    ) -> None:
        """Give a mocked device the needed properties."""
        self.mac = DISCOVERY_INFO.properties["PlcMacAddress"] if self.plcnet else None
        self.mt_number = DISCOVERY_INFO.properties["MT"]
        self.product = DISCOVERY_INFO.properties["Product"]
        self.serial_number = DISCOVERY_INFO.properties["SN"]

    def reset(self):
        """Reset mock to starting point."""
        self._firmware_version = DISCOVERY_INFO.properties["FirmwareVersion"]
        self.async_disconnect = AsyncMock()
        self.device = DeviceApi(IP, None, DISCOVERY_INFO)
        self.device.async_check_firmware_available = AsyncMock(
            return_value=FIRMWARE_UPDATE_AVAILABLE
        )
        self.device.async_get_led_setting = AsyncMock(return_value=False)
        self.device.async_restart = AsyncMock(return_value=True)
        self.device.async_uptime = AsyncMock(return_value=UPTIME)
        self.device.async_start_wps = AsyncMock(return_value=True)
        self.device.async_get_wifi_connected_station = AsyncMock(
            return_value=CONNECTED_STATIONS
        )
        self.device.async_get_wifi_guest_access = AsyncMock(return_value=GUEST_WIFI)
        self.device.async_get_wifi_neighbor_access_points = AsyncMock(
            return_value=NEIGHBOR_ACCESS_POINTS
        )
        self.device.async_start_firmware_update = AsyncMock(return_value=True)
        self.plcnet = PlcNetApi(IP, None, DISCOVERY_INFO)
        self.plcnet.async_get_network_overview = AsyncMock(return_value=PLCNET)
        self.plcnet.async_identify_device_start = AsyncMock(return_value=True)
        self.plcnet.async_pair_device = AsyncMock(return_value=True)
