"""Coordinator for the Sunsynk integration."""

import asyncio
from dataclasses import dataclass
from typing import override

from sunsynk.battery import Battery
from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from sunsynk.grid import Grid
from sunsynk.input import Input
from sunsynk.inverter import Inverter
from sunsynk.load import Load

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type SunsynkConfigEntry = ConfigEntry[SunsynkDataUpdateCoordinator]


@dataclass
class SunsynkInverterData:
    """Realtime data for one inverter."""

    inverter: Inverter
    battery: Battery
    grid: Grid
    load: Load
    solar: Input


class SunsynkDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, SunsynkInverterData]]
):
    """Fetch data for all inverters of a Sunsynk account."""

    config_entry: SunsynkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SunsynkConfigEntry,
        client: SunsynkClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_fetch_inverter(self, inverter: Inverter) -> SunsynkInverterData:
        """Fetch the realtime data for one inverter."""
        battery, grid, load, solar = await asyncio.gather(
            self.client.get_inverter_realtime_battery(inverter.sn),
            self.client.get_inverter_realtime_grid(inverter.sn),
            self.client.get_inverter_realtime_load(inverter.sn),
            self.client.get_inverter_realtime_input(inverter.sn),
        )
        return SunsynkInverterData(
            inverter=inverter,
            battery=battery,
            grid=grid,
            load=load,
            solar=solar,
        )

    @override
    async def _async_update_data(self) -> dict[str, SunsynkInverterData]:
        """Fetch data from the Sunsynk API."""
        try:
            inverters = await self.client.get_inverters()
            data = await asyncio.gather(
                *(self._async_fetch_inverter(inverter) for inverter in inverters)
            )
        except SunsynkAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except SunsynkConnectionError as err:
            raise UpdateFailed(err) from err
        return {inverter_data.inverter.sn: inverter_data for inverter_data in data}
