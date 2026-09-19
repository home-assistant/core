"""Data update coordinator for Comet WiFi thermostats."""

from asyncio import sleep
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from aiocometwifi import CometWifiError, Thermostat

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FETCH_DATA_TIMEOUT, LOGGER, POLL_INTERVAL

type CometWiFiConfigEntry = ConfigEntry[CometWiFiDataCoordinator]


@dataclass
class CometWiFiData:
    """Data from Comet WiFi device."""

    temperature_setpoint: float
    temperature_ambient: float
    is_heating: bool


class CometWiFiDataCoordinator(DataUpdateCoordinator[CometWiFiData]):
    """Class to manage fetching Comet WiFi data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CometWiFiConfigEntry,
        client: Thermostat,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN} {client.mac}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client
        self.mac = client.mac
        self.last_heating_setpoint: float | None = None

    @override
    async def _async_setup(self) -> None:
        """Subscribe to topics for the thermostat."""
        try:
            await self.client.connect()
        except CometWifiError as err:
            raise UpdateFailed(f"Error connecting to {self.mac}: {err}") from err

    @override
    async def _async_update_data(self) -> CometWiFiData:
        """Fetch data from Comet WiFi device."""
        try:
            await self.client.update_heating_values()
        except CometWifiError as err:
            raise UpdateFailed(f"Error requesting data from {self.mac}: {err}") from err

        # Give the device some time to answer
        await sleep(FETCH_DATA_TIMEOUT)
        if not self.client.connected:
            raise UpdateFailed(f"No reply from {self.mac}.")

        # Remember setpoint that turning on can restore it.
        if self.client.is_heating:
            self.last_heating_setpoint = self.client.setpoint

        return CometWiFiData(
            temperature_setpoint=self.client.setpoint,
            temperature_ambient=self.client.temperature_ambient,
            is_heating=self.client.is_heating,
        )
