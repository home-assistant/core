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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Delay before refreshing after a state change to allow device to process
# and avoid race conditions with rapid sequential changes
REQUEST_REFRESH_DELAY = 1.5

# Default update interval in minutes (matches upstream Throttle value)
DEFAULT_UPDATE_INTERVAL = 15


class MelCloudDevice:
    """MELCloud Device instance."""

    def __init__(
        self, device: Device, coordinator: MelCloudDeviceUpdateCoordinator
    ) -> None:
        """Construct a device wrapper."""
        self.device = device
        self.name = device.name
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.device_available

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


class MelCloudDeviceUpdateCoordinator(DataUpdateCoordinator[MelCloudDevice]):
    """Per-device coordinator for MELCloud data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the per-device coordinator."""
        self._device = device
        self.device_available = True

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{device.name}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
            always_update=False,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DELAY,
                immediate=False,
            ),
        )

        # Create the wrapper after coordinator is initialized
        self.mel_device = MelCloudDevice(device, self)

    async def _async_update_data(self) -> MelCloudDevice:
        """Fetch data for this specific device from MELCloud."""
        try:
            await self._device.update()
            self.device_available = True
        except ClientResponseError as ex:
            if ex.status in (401, 403):
                raise ConfigEntryAuthFailed from ex
            if ex.status == 429:
                _LOGGER.error(
                    "MELCloud rate limit exceeded for %s. Your account may be "
                    "temporarily blocked",
                    self._device.name,
                )
            else:
                _LOGGER.warning("Error updating %s: %s", self._device.name, ex)
            self.device_available = False
        except ClientConnectionError as ex:
            _LOGGER.warning("Connection failed for %s: %s", self._device.name, ex)
            self.device_available = False

        return self.mel_device

    async def async_set(self, properties: dict[str, Any]) -> None:
        """Write state changes to the MELCloud API."""
        try:
            await self._device.set(properties)
            self.device_available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self._device.name)
            self.device_available = False

        await self.async_request_refresh()


type MelCloudConfigEntry = ConfigEntry[dict[str, list[MelCloudDeviceUpdateCoordinator]]]


async def mel_devices_setup(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, list[MelCloudDeviceUpdateCoordinator]]:
    """Set up MELCloud devices and create per-device coordinators."""
    token = config_entry.data[CONF_TOKEN]
    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(10):
            all_devices = await get_devices(
                token,
                session,
                conf_update_interval=timedelta(minutes=30),
                device_set_debounce=timedelta(seconds=2),
            )
    except ClientResponseError as ex:
        if ex.status in (401, 403):
            raise ConfigEntryAuthFailed from ex
        if ex.status == 429:
            raise UpdateFailed(
                "MELCloud rate limit exceeded. Your account may be temporarily blocked"
            ) from ex
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex

    # Create per-device coordinators
    coordinators: dict[str, list[MelCloudDeviceUpdateCoordinator]] = {}
    device_registry = dr.async_get(hass)
    for device_type, devices in all_devices.items():
        coordinators[device_type] = []
        for device in devices:
            coordinator = MelCloudDeviceUpdateCoordinator(hass, device, config_entry)
            # Perform initial refresh for this device
            await coordinator.async_config_entry_first_refresh()
            coordinators[device_type].append(coordinator)
            # Register parent device now so zone entities can reference it via via_device
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                **coordinator.mel_device.device_info,
            )

    return coordinators
