"""Data update coordinator for the EHEIM Digital integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientError
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import EheimDeviceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AsyncSetupDeviceEntitiesCallback = Callable[[str], Coroutine[Any, Any, None]]


class EheimDigitalUpdateCoordinator(
    DataUpdateCoordinator[dict[str, EheimDigitalDevice]]
):
    """The EHEIM Digital data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the EHEIM Digital data update coordinator."""
        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        self.hub = EheimDigitalHub(
            host=self.config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
            loop=hass.loop,
            receive_callback=self._async_receive_callback,
            device_found_callback=self._async_device_found,
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
                await platform_callback(device_address)

    async def _async_receive_callback(self) -> None:
        self.async_set_updated_data(self.hub.devices)

    async def _async_setup(self) -> None:
        await self.hub.connect()
        await self.hub.update()

    async def _async_update_data(self) -> dict[str, EheimDigitalDevice]:
        try:
            await self.hub.update()
        except ClientError as ex:
            raise UpdateFailed from ex
        return self.data
