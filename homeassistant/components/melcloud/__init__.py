"""The MELCloud Climate integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import Device, get_devices
from pymelcloud.atw_device import Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with MELClooud."""
    conf = entry.data
    try:
        mel_devices = await mel_devices_setup(hass, conf[CONF_TOKEN])
    except ClientResponseError as ex:
        if isinstance(ex, ClientResponseError) and ex.code == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: mel_devices})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok


class MelCloudDevice:
    """MELCloud Device instance."""

    def __init__(self, device: Device) -> None:
        """Construct a device wrapper."""
        self.device = device
        self.name = device.name
        self._available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Pull the latest data from MELCloud."""
        try:
            await self.device.update()
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False

    async def async_set(self, properties: dict[str, Any]):
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
    def device_id(self):
        """Return device ID."""
        return self.device.device_id

    @property
    def building_id(self):
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


async def mel_devices_setup(
    hass: HomeAssistant, token: str
) -> dict[str, list[MelCloudDevice]]:
    """Query connected devices from MELCloud."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(10):
        all_devices = await get_devices(
            token,
            session,
            conf_update_interval=timedelta(minutes=30),
            device_set_debounce=timedelta(seconds=2),
        )
    wrapped_devices: dict[str, list[MelCloudDevice]] = {}
    for device_type, devices in all_devices.items():
        wrapped_devices[device_type] = [MelCloudDevice(device) for device in devices]
    return wrapped_devices
