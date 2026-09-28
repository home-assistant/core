"""Coordinator for handling data fetching and updates."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

import aiohttp
from lunatone_rest_api_client import DALIScan, Device, Devices, Info, Sensor, Sensors
from lunatone_rest_api_client.models import InfoData, ScanData, ScanLineData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_INFO_UPDATE_INTERVAL = timedelta(seconds=60)
DEFAULT_DEVICES_UPDATE_INTERVAL = timedelta(seconds=10)
DEFAULT_SENSORS_UPDATE_INTERVAL = timedelta(seconds=30)
DEFAULT_SCAN_UPDATE_INTERVAL = timedelta(seconds=10)


@dataclass
class LunatoneData:
    """Data for Lunatone integration."""

    coordinator_info: LunatoneInfoDataUpdateCoordinator
    coordinator_devices: LunatoneDevicesDataUpdateCoordinator
    coordinator_scan: LunatoneScanDataUpdateCoordinator
    coordinator_sensors: LunatoneSensorsDataUpdateCoordinator | None = None


type LunatoneConfigEntry = ConfigEntry[LunatoneData]


class LunatoneInfoDataUpdateCoordinator(DataUpdateCoordinator[InfoData]):
    """Data update coordinator for Lunatone info."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LunatoneConfigEntry, info_api: Info
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-info",
            always_update=False,
            update_interval=DEFAULT_INFO_UPDATE_INTERVAL,
        )
        self.info_api = info_api
        self.previous_devices: set[int] = set()

    @override
    async def _async_update_data(self) -> InfoData:
        """Update info data."""
        try:
            await self.info_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve info data from Lunatone REST API"
            ) from ex

        if self.info_api.data is None:
            raise UpdateFailed("Did not receive info data from Lunatone REST API")

        data = self.info_api.data

        current_devices = set(map(int, data.lines))
        if stale_devices := self.previous_devices - current_devices:
            device_registry = dr.async_get(self.hass)
            for device_id in stale_devices:
                device = device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{self.config_entry.unique_id}-line{device_id}"),
                    self.config_entry.entry_id,
                )
                if device:
                    device_registry.async_remove_device(device.id)
        self.previous_devices = current_devices

        return data


class LunatoneDevicesDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, dict[int, Device]]]
):
    """Data update coordinator for Lunatone devices."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        devices_api: Devices,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-devices",
            always_update=False,
            update_interval=DEFAULT_DEVICES_UPDATE_INTERVAL,
        )
        self.devices_api = devices_api
        self.previous_devices: set[int] = set()

    @override
    async def _async_update_data(self) -> dict[int, dict[int, Device]]:
        """Update devices data."""
        try:
            await self.devices_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve devices data from Lunatone REST API"
            ) from ex

        data: dict[int, dict[int, Device]] = defaultdict(dict)
        for device in self.devices_api.devices.values():
            data[device.data.line].update({device.data.id: device})

        current_devices = {k for inner in data.values() for k in inner}
        if stale_devices := self.previous_devices - current_devices:
            device_registry = dr.async_get(self.hass)
            for device_id in stale_devices:
                device_ = device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{self.config_entry.unique_id}-device{device_id}"),
                    self.config_entry.entry_id,
                )
                if device_:
                    device_registry.async_remove_device(device_.id)
        self.previous_devices = current_devices

        return dict(data)


class LunatoneSensorsDataUpdateCoordinator(DataUpdateCoordinator[dict[int, Sensor]]):
    """Data update coordinator for Lunatone sensors."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        sensors_api: Sensors,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-sensors",
            always_update=False,
            update_interval=DEFAULT_SENSORS_UPDATE_INTERVAL,
        )
        self.sensors_api = sensors_api
        self.previous_devices: set[tuple[int, int]] = set()

    @override
    async def _async_update_data(self) -> dict[int, Sensor]:
        """Update sensor data."""
        try:
            await self.sensors_api.async_refresh()
            await self.sensors_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve sensors data from Lunatone REST API"
            ) from ex

        data = self.sensors_api.sensors

        assert self.config_entry.unique_id is not None

        current_devices = {
            (
                sensor.data.dali_sensor_address.line,
                sensor.data.dali_sensor_address.address,
            )
            for sensor in data.values()
            if sensor.data.dali_sensor_address is not None
        }
        if stale_devices := self.previous_devices - current_devices:
            device_registry = dr.async_get(self.hass)
            for line_id, address in stale_devices:
                device = device_registry.async_get_device_by_identifier(
                    (
                        DOMAIN,
                        (
                            f"{self.config_entry.unique_id}-line{line_id}"
                            f"-d24-address{address}"
                        ),
                    ),
                    self.config_entry.entry_id,
                )
                if device:
                    device_registry.async_remove_device(device.id)
        self.previous_devices = current_devices

        return data


class LunatoneScanDataUpdateCoordinator(DataUpdateCoordinator[ScanData]):
    """Data update coordinator for Lunatone scan."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        dali_scan_api: DALIScan,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-scan",
            always_update=False,
            update_interval=DEFAULT_SCAN_UPDATE_INTERVAL,
        )
        self.dali_scan_api = dali_scan_api
        self.line_scan_status: dict[int, ScanLineData] = {}

    @override
    async def _async_update_data(self) -> ScanData:
        """Update scan data."""
        try:
            await self.dali_scan_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve scan data from Lunatone REST API"
            ) from ex

        update_interval = DEFAULT_SCAN_UPDATE_INTERVAL
        if self.dali_scan_api.data.busy:
            update_interval = timedelta(seconds=1)
        self.update_interval = update_interval

        self.line_scan_status = {
            scan_data.line: scan_data for scan_data in self.dali_scan_api.data.lines
        }
        return self.dali_scan_api.data
