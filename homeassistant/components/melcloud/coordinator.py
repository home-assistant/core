"""DataUpdateCoordinator for the MELCloud integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import Device, get_devices
from pymelcloud.atw_device import Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Delay before refreshing after a state change to allow device to process
# and avoid race conditions with rapid sequential changes
REQUEST_REFRESH_DELAY = 1.5


class MelCloudDevice:
    """MELCloud Device instance."""

    def __init__(self, device: Device) -> None:
        """Construct a device wrapper."""
        self.device = device
        self.name = device.name
        self._available = True

    @property
    def device_conf(self) -> dict[str, Any]:
        """Return device configuration from MELCloud."""
        device_conf = self.device._device_conf  # noqa: SLF001
        if device_conf is None:
            return {}
        return device_conf.get("Device", {})

    @property
    def wifi_signal(self) -> int | None:
        """Return WiFi signal strength."""
        return self.device_conf.get("WifiSignalStrength")

    @property
    def has_wifi_signal(self) -> bool:
        """Return True if WiFi signal is available."""
        return self.wifi_signal is not None

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Return extra device attributes."""
        data: dict[str, Any] = {
            "device_id": self.device.device_id,
            "serial": self.device.serial,
            "mac": self.device.mac,
        }
        if (unit_infos := self.device.units) is not None:
            for i, unit in enumerate(unit_infos[:2]):
                data[f"unit_{i}_model"] = unit.get("model")
                data[f"unit_{i}_serial"] = unit.get("serial")
        return data

    async def async_set(self, properties: dict[str, Any]) -> None:
        """Write state changes to the MELCloud API."""
        try:
            await self.device.set(properties)
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_id(self) -> str:
        """Return device ID."""
        return self.device.device_id

    @property
    def building_id(self) -> str:
        """Return building ID of the device."""
        return self.device.building_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        model = None
        if (unit_infos := self.device.units) is not None:
            model = ", ".join([x["model"] for x in unit_infos if x["model"]])
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, f"{self.device.mac}-{self.device.serial}")},
            manufacturer="Mitsubishi Electric",
            model=model,
            name=self.name,
        )

    def zone_device_info(self, zone: Zone) -> DeviceInfo:
        """Return a zone device description for device registry."""
        dev = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{dev.mac}-{dev.serial}-{zone.zone_index}")},
            manufacturer="Mitsubishi Electric",
            model="ATW zone device",
            name=f"{self.name} {zone.name}",
            via_device=(DOMAIN, f"{dev.mac}-{dev.serial}"),
        )


class MelCloudDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[MelCloudDevice]]]
):
    """Coordinator for MELCloud data updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        scan_interval_minutes = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
            always_update=False,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DELAY,
                immediate=False,
            ),
        )
        self._session = async_get_clientsession(hass)
        self._devices: dict[str, list[MelCloudDevice]] = {}

    async def _async_setup(self) -> None:
        """Set up the coordinator by fetching initial device list."""
        token = self.config_entry.data[CONF_TOKEN]
        try:
            async with asyncio.timeout(10):
                all_devices = await get_devices(
                    token,
                    self._session,
                    conf_update_interval=timedelta(minutes=30),
                    device_set_debounce=timedelta(seconds=2),
                )
        except ClientResponseError as ex:
            if ex.status in (401, 403):
                raise ConfigEntryAuthFailed from ex
            if ex.status == 429:
                raise UpdateFailed(
                    "MELCloud rate limit exceeded. Your account may be temporarily "
                    "blocked. Consider increasing the update interval in integration "
                    "options (Settings > Devices & Services > MELCloud > Configure)"
                ) from ex
            raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex
        except (TimeoutError, ClientConnectionError) as ex:
            raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex

        self._devices = {
            device_type: [MelCloudDevice(device) for device in devices]
            for device_type, devices in all_devices.items()
        }

    async def _async_update_data(self) -> dict[str, list[MelCloudDevice]]:
        """Fetch data from MELCloud."""
        if not self._devices:
            await self._async_setup()

        for devices in self._devices.values():
            for mel_device in devices:
                try:
                    await mel_device.device.update()
                    mel_device._available = True  # noqa: SLF001
                except ClientResponseError as ex:
                    if ex.status in (401, 403):
                        raise ConfigEntryAuthFailed from ex
                    if ex.status == 429:
                        _LOGGER.error(
                            "MELCloud rate limit exceeded for %s. Your account may be "
                            "temporarily blocked. Consider increasing the update interval "
                            "in integration options (Settings > Devices & Services > "
                            "MELCloud > Configure)",
                            mel_device.name,
                        )
                    else:
                        _LOGGER.warning("Error updating %s: %s", mel_device.name, ex)
                    mel_device._available = False  # noqa: SLF001
                except ClientConnectionError as ex:
                    _LOGGER.warning("Connection failed for %s: %s", mel_device.name, ex)
                    mel_device._available = False  # noqa: SLF001

        return self._devices
