"""Coordinator for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REG_CURRENT_TEMP,
    REG_SESSION_ACTIVE,
    WRITE_SETTLE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class LeilSaunaCoordinator(DataUpdateCoordinator[dict[str, int | float | None]]):
    """Coordinator for fetching Saunum Leil Sauna data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncModbusTcpClient,
        device_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client
        self.device_id = device_id
        # Track whether we have already logged that the device is unavailable.
        # We log a single INFO message when the device first becomes unavailable
        # and another INFO message when communication is restored, per HA
        # unavailability logging guidelines.
        self._unavailable_logged: bool = False

    async def _async_update_data(self) -> dict[str, int | float | None]:
        """Fetch data from the sauna controller."""
        try:
            # Read essential registers for climate control (session_active and target_temperature)
            holding_result = await self.client.read_holding_registers(
                address=REG_SESSION_ACTIVE,
                count=5,
                device_id=self.device_id,
            )
            if holding_result.isError():
                raise UpdateFailed("holding register read error")
            holding_regs = holding_result.registers

            # Read temperature sensor and heater status
            sensor_result = await self.client.read_holding_registers(
                address=REG_CURRENT_TEMP,
                count=4,
                device_id=self.device_id,
            )
            if sensor_result.isError():
                raise UpdateFailed("sensor register read error")
            sensor_regs = sensor_result.registers

            data: dict[str, int | float | None] = {
                "session_active": holding_regs[0],
                "target_temperature": holding_regs[4],
                "current_temperature": sensor_regs[0],
                "heater_status": sensor_regs[3],
            }
        except (ModbusException, TimeoutError) as err:
            if not self._unavailable_logged:
                _LOGGER.info("Device became unavailable: %s", err)
                self._unavailable_logged = True
            raise UpdateFailed(f"communication error: {err}") from err
        else:
            if self._unavailable_logged:
                _LOGGER.info("Device communication restored")
                self._unavailable_logged = False
            return data

    async def async_write_register(self, address: int, value: int) -> bool:
        """Write a single holding register."""
        try:
            # Ensure client is connected before writing
            if not self.client.connected:
                await self.client.connect()
                if not self.client.connected:
                    _LOGGER.error(
                        "Failed to connect to device for writing register %d", address
                    )
                    return False

            result = await self.client.write_register(
                address=address,
                value=value,
                device_id=self.device_id,
            )
        except ModbusException as err:
            _LOGGER.error("Error writing register %d: %s", address, err)
            return False
        else:
            if result.isError():
                _LOGGER.error("Error writing register %d: %s", address, result)
                return False
            # Give the device time to process the write before refreshing
            await asyncio.sleep(WRITE_SETTLE_SECONDS)
            # Refresh data after write
            await self.async_request_refresh()
            return True

    async def async_write_registers(self, writes: list[tuple[int, int]]) -> bool:
        """Write multiple holding registers with one final refresh.

        Each item in writes is (address, value). Written sequentially. Any failure
        logs an error; successful writes continue. A single refresh occurs after all
        attempts to minimize polling churn. Returns True only if all writes succeed.
        """
        if not writes:
            return True

        # Ensure client is connected before writing
        if not self.client.connected:
            await self.client.connect()
            if not self.client.connected:
                _LOGGER.error("Failed to connect to device for writing registers")
                return False

        all_ok = True
        for address, value in writes:
            try:
                result = await self.client.write_register(
                    address=address,
                    value=value,
                    device_id=self.device_id,
                )
            except ModbusException as err:
                _LOGGER.error("Error writing register %d: %s", address, err)
                all_ok = False
                continue
            else:
                if result.isError():
                    _LOGGER.error("Error writing register %d: %s", address, result)
                    all_ok = False
                    continue
        # Give device time once
        await asyncio.sleep(WRITE_SETTLE_SECONDS)
        await self.async_request_refresh()
        return all_ok
