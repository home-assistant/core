"""The MELCloud Climate integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from async_timeout import timeout
from pymelcloud import Device, get_devices
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

CONF_LANGUAGE = "language"
CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_TOKEN): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Establish connection with MELCloud."""
    if DOMAIN not in config:
        return True

    username = config[DOMAIN][CONF_USERNAME]
    token = config[DOMAIN][CONF_TOKEN]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_USERNAME: username, CONF_TOKEN: token},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with MELClooud."""
    conf = entry.data
    mel_devices = await mel_devices_setup(hass, conf[CONF_TOKEN])
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
        self._coordinator: DataUpdateCoordinator | None = None

    async def async_create_coordinator(self, hass: HomeAssistant) -> None:
        """Create the coordinator for a specific device."""
        if self._coordinator:
            return

        coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.name}",
            update_method=self.device.update,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        await coordinator.async_refresh()
        self._coordinator = coordinator

    async def async_set(self, properties: dict[str, Any]) -> None:
        """Write state changes to the MELCloud API."""
        try:
            await self.device.set(properties)
        except (ClientConnectionError, ClientResponseError):
            _LOGGER.warning("Connection failed for %s", self.name)
            return
        if self._coordinator:
            self._coordinator.async_set_updated_data(None)

    @property
    def coordinator(self) -> DataUpdateCoordinator | None:
        """Return coordinator associated."""
        return self._coordinator

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

    @property
    def daily_energy_consumed(self) -> float | None:
        """Return energy consumed during the current day in kWh."""
        return self.device.daily_energy_consumed


async def mel_devices_setup(hass, token) -> dict[str, list[MelCloudDevice]]:
    """Query connected devices from MELCloud."""
    session = async_get_clientsession(hass)
    try:
        async with timeout(10):
            all_devices = await get_devices(
                token,
                session,
                conf_update_interval=timedelta(minutes=5),
                device_set_debounce=timedelta(seconds=1),
            )
    except (asyncio.TimeoutError, ClientConnectionError, ClientResponseError) as ex:
        raise ConfigEntryNotReady() from ex

    wrapped_devices: dict[str, list[MelCloudDevice]] = {}
    for device_type, devices in all_devices.items():
        wrapped_types = []
        for device in devices:
            mel_device = MelCloudDevice(device)
            await mel_device.async_create_coordinator(hass)
            wrapped_types.append(mel_device)
        wrapped_devices[device_type] = wrapped_types
    return wrapped_devices
