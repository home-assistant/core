"""Data update coordinator for the EHEIM Digital integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from aiohttp import ClientError
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import EheimDeviceType, EheimDigitalClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AsyncSetupDeviceEntitiesCallback = Callable[[dict[str, EheimDigitalDevice]], None]

type EheimDigitalConfigEntry = ConfigEntry[EheimDigitalUpdateCoordinator]


class EheimDigitalUpdateCoordinator(
    DataUpdateCoordinator[dict[str, EheimDigitalDevice]]
):
    """The EHEIM Digital data update coordinator."""

    config_entry: EheimDigitalConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: EheimDigitalConfigEntry
    ) -> None:
        """Initialize the EHEIM Digital data update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.main_device_added_event = asyncio.Event()
        self.hub = EheimDigitalHub(
            host=self.config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
            loop=hass.loop,
            receive_callback=self._async_receive_callback,
            device_found_callback=self._async_device_found,
            main_device_added_event=self.main_device_added_event,
        )
        self.known_devices: set[str] = set()
        self.platform_callbacks: set[AsyncSetupDeviceEntitiesCallback] = set()

    def add_platform_callback(
        self,
        async_setup_device_entities: AsyncSetupDeviceEntitiesCallback,
    ) -> None:
        """Add the setup callbacks from a specific platform."""
        self.platform_callbacks.add(async_setup_device_entities)

    async def _async_device_found(
        self, device_address: str, device_type: EheimDeviceType
    ) -> None:
        """Set up a new device found.

        This function is called from the library whenever a new device is added.
        """

        if device_address not in self.known_devices:
            for platform_callback in self.platform_callbacks:
                platform_callback({device_address: self.hub.devices[device_address]})

    async def _async_receive_callback(self) -> None:
        self.async_set_updated_data(self.hub.devices)

    async def _async_setup(self) -> None:
        try:
            await self.hub.connect()
            async with asyncio.timeout(2):
                # This event gets triggered when the first message is received from
                # the device, it contains the data necessary to create the main device.
                # This removes the race condition where the main device is accessed
                # before the response from the device is parsed.
                await self.main_device_added_event.wait()
            await self.hub.update()
        except (TimeoutError, EheimDigitalClientError) as err:
            raise ConfigEntryNotReady from err

    async def _async_update_data(self) -> dict[str, EheimDigitalDevice]:
        try:
            await self.hub.update()
        except ClientError as ex:
            raise UpdateFailed from ex
        return self.data
