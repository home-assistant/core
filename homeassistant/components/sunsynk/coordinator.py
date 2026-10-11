"""Coordinators for the Sunsynk integration."""

import asyncio
from dataclasses import dataclass
from typing import override

from modbus_connection import ModbusError
from sunsynk.battery import Battery
from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from sunsynk.grid import Grid
from sunsynk.input import Input
from sunsynk.inverter import Inverter
from sunsynk.load import Load
from sunsynk_modbus import SunsynkInverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, MODBUS_SCAN_INTERVAL, SCAN_INTERVAL

type SunsynkConfigEntry = ConfigEntry[
    list[SunsynkDataUpdateCoordinator] | SunsynkModbusCoordinator
]


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


class SunsynkModbusCoordinator(DataUpdateCoordinator[SunsynkInverter]):
    """Poll one Sunsynk inverter over Modbus."""

    config_entry: SunsynkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SunsynkConfigEntry,
        inverter: SunsynkInverter,
        serial_number: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{serial_number}_modbus",
            update_interval=MODBUS_SCAN_INTERVAL,
        )
        self.inverter = inverter
        self.serial_number = serial_number

    @override
    async def _async_update_data(self) -> SunsynkInverter:
        """Read the inverter's registers."""
        try:
            report = await self.inverter.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err)},
            ) from err
        if report.failed:
            name, error = next(iter(report.failed.items()))
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": f"{name}: {error}"},
            ) from error
        return self.inverter
