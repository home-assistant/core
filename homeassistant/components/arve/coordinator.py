"""Coordinator for the Arve integration."""

from __future__ import annotations

from datetime import timedelta

from asyncarve import (
    Arve,
    ArveConnectionError,
    ArveDeviceInfo,
    ArveDevices,
    ArveError,
    ArveSensProData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type ArveConfigEntry = ConfigEntry[ArveCoordinator]


class ArveCoordinator(DataUpdateCoordinator[ArveSensProData]):
    """Arve coordinator."""

    config_entry: ArveConfigEntry
    devices: ArveDevices

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Arve coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

        self.arve = Arve(
            self.config_entry.data[CONF_ACCESS_TOKEN],
            self.config_entry.data[CONF_CLIENT_SECRET],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[str, ArveDeviceInfo]:
        """Fetch data from API endpoint."""
        try:
            self.devices = await self.arve.get_devices()

            response_data = {
                sn: ArveDeviceInfo(
                    await self.arve.device_sensor_data(sn),
                    await self.arve.get_sensor_info(sn),
                )
                for sn in self.devices.sn
            }
        except ArveConnectionError as err:
            raise UpdateFailed("Unable to connect to the Arve device") from err
        except ArveError as err:
            raise UpdateFailed("Unknown error occurred") from err

        return response_data
