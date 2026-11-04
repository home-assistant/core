"""Coordinator for handling data fetching and updates."""

from dataclasses import dataclass
from datetime import timedelta
import logging
import re
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


def find_devices(
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    device_identifier_pattern: re.Pattern[str],
) -> set[str]:
    """Return matching device unique IDs in the device registry for this config entry."""
    devices: set[str] = set()
    for device in dr.async_entries_for_config_entry(device_registry, config_entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and device_identifier_pattern.fullmatch(identifier):
                devices.add(identifier)
    return devices


def remove_devices(
    device_registry: dr.DeviceRegistry, config_entry_id: str, devices: set[str]
) -> None:
    """Remove devices from the device registry."""
    for device_unique_id in devices:
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_unique_id), config_entry_id
        )
        if device:
            device_registry.async_remove_device(device.id)


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

        assert config_entry.unique_id is not None
        device_registry = dr.async_get(hass)
        self.previous_devices: set[str] = find_devices(
            device_registry,
            config_entry.entry_id,
            re.compile(rf"{re.escape(config_entry.unique_id)}-line\d+"),
        )

    @override
    async def _async_update_data(self) -> InfoData:
        """Update info data."""
        try:
            await self.info_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_retrieve_info_data"
            ) from ex

        if self.info_api.data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="missing_info_data"
            )

        data = self.info_api.data

        device_registry = dr.async_get(self.hass)
        assert self.config_entry.unique_id is not None
        current_devices = {
            f"{self.config_entry.unique_id}-line{line_id}" for line_id in data.lines
        }
        stale_devices = self.previous_devices - current_devices
        remove_devices(device_registry, self.config_entry.entry_id, stale_devices)
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

        assert config_entry.unique_id is not None
        device_registry = dr.async_get(hass)
        self.previous_devices: set[str] = find_devices(
            device_registry,
            config_entry.entry_id,
            re.compile(rf"{re.escape(config_entry.unique_id)}-device\d+"),
        )

    @override
    async def _async_update_data(self) -> dict[int, dict[int, Device]]:
        """Update devices data."""
        try:
            await self.devices_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_devices_data",
            ) from ex

        data: dict[int, dict[int, Device]] = {}
        for d in self.devices_api.devices.values():
            data.setdefault(d.data.line, {})[d.data.id] = d

        device_registry = dr.async_get(self.hass)
        assert self.config_entry.unique_id is not None
        current_devices = {
            f"{self.config_entry.unique_id}-device{device_id}"
            for devices in data.values()
            for device_id in devices
        }
        stale_devices = self.previous_devices - current_devices
        remove_devices(device_registry, self.config_entry.entry_id, stale_devices)
        self.previous_devices = current_devices

        return data


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

        assert config_entry.unique_id is not None
        device_registry = dr.async_get(hass)
        self.previous_devices: set[str] = find_devices(
            device_registry,
            config_entry.entry_id,
            re.compile(rf"{re.escape(config_entry.unique_id)}-line\d+-d24-address\d+"),
        )

    @override
    async def _async_update_data(self) -> dict[int, Sensor]:
        """Update sensor data."""
        try:
            await self.sensors_api.async_refresh()
            await self.sensors_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_sensors_data",
            ) from ex

        data = self.sensors_api.sensors

        device_registry = dr.async_get(self.hass)
        assert self.config_entry.unique_id is not None
        current_devices = {
            (
                f"{self.config_entry.unique_id}"
                f"-line{sensor.data.dali_sensor_address.line}"
                f"-d24-address{sensor.data.dali_sensor_address.address}"
            )
            for sensor in data.values()
            if sensor.data.dali_sensor_address is not None
        }
        stale_devices = self.previous_devices - current_devices
        remove_devices(device_registry, self.config_entry.entry_id, stale_devices)
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
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_scan_data",
            ) from ex

        update_interval = DEFAULT_SCAN_UPDATE_INTERVAL
        if self.dali_scan_api.data.busy:
            update_interval = timedelta(seconds=1)
        self.update_interval = update_interval

        self.line_scan_status = {
            scan_data.line: scan_data for scan_data in self.dali_scan_api.data.lines
        }
        return self.dali_scan_api.data
