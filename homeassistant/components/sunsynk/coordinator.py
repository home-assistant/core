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

type SunsynkConfigEntry = ConfigEntry[list[SunsynkDataUpdateCoordinator]]


@dataclass
class SunsynkInverterData:
    """Realtime data for one inverter."""

    battery: Battery
    grid: Grid
    load: Load
    solar: Input


class SunsynkDataUpdateCoordinator(DataUpdateCoordinator[SunsynkInverterData]):
    """Fetch the realtime data of one Sunsynk inverter."""

    config_entry: SunsynkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SunsynkConfigEntry,
        client: SunsynkClient,
        inverter: Inverter,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{inverter.sn}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.inverter = inverter

    @override
    async def _async_update_data(self) -> SunsynkInverterData:
        """Fetch data from the Sunsynk API."""
        serial_number = self.inverter.sn
        try:
            battery, grid, load, solar = await asyncio.gather(
                self.client.get_inverter_realtime_battery(serial_number),
                self.client.get_inverter_realtime_grid(serial_number),
                self.client.get_inverter_realtime_load(serial_number),
                self.client.get_inverter_realtime_input(serial_number),
            )
        except SunsynkAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except SunsynkConnectionError as err:
            raise UpdateFailed(err) from err
        return SunsynkInverterData(battery=battery, grid=grid, load=load, solar=solar)
