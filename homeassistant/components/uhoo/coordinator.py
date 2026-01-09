"""Custom uhoo data update coordinator."""

import asyncio

from aiohttp.client_exceptions import ClientConnectorDNSError
from uhooapi import Client, Device
from uhooapi.errors import UhooError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type UhooConfigEntry = ConfigEntry["UhooDataUpdateCoordinator"]


class UhooDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from the uHoo API."""

    def __init__(
        self, hass: HomeAssistant, client: Client, entry: UhooConfigEntry
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self.client = client
        self.entry = entry
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, Device]:
        try:
            await self.client.login()
            if self.client.devices:
                await asyncio.gather(
                    *[
                        self.client.get_latest_data(device_id)
                        for device_id in self.client.devices
                    ]
                )
        except TimeoutError as error:
            raise UpdateFailed from error
        except ClientConnectorDNSError as error:
            raise UpdateFailed from error
        except UhooError as error:
            raise UpdateFailed(f"The device is unavailable: {error}") from error
        else:
            return self.client.devices
