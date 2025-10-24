"""Coordinator for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
        self._session_start_time: datetime | None = None
        # Track whether we have already logged that the device is unavailable.
        # We log a single INFO message when the device first becomes unavailable
        # and another INFO message when communication is restored, per HA
        # unavailability logging guidelines.
        self._unavailable_logged: bool = False
        # Track alarm register availability to log once when not supported
        self._alarm_registers_unavailable_logged: bool = False

    async def _async_update_data(self) -> dict[str, int | float | None]:
        """Fetch data from the sauna controller."""
        try:
            holding_result = await self.client.read_holding_registers(
                address=REG_SESSION_ACTIVE,
                count=7,
                device_id=self.device_id,
            )
            if holding_result.isError():
                raise UpdateFailed("holding register read error")
            holding_regs = holding_result.registers

            sensor_result = await self.client.read_holding_registers(
                address=REG_CURRENT_TEMP,
                count=5,
                device_id=self.device_id,
            )
            if sensor_result.isError():
                raise UpdateFailed("sensor register read error")
            sensor_regs = sensor_result.registers

            alarm_regs = [0, 0, 0, 0, 0, 0]
            try:
                alarm_result = await self.client.read_holding_registers(
                    address=200,
                    count=6,
                    device_id=self.device_id,
                )
                if not alarm_result.isError():
                    alarm_regs = alarm_result.registers
                elif not self._alarm_registers_unavailable_logged:
                    _LOGGER.info(
                        "Alarm registers not available on this device: %s",
                        alarm_result,
                    )
                    self._alarm_registers_unavailable_logged = True
                else:
                    _LOGGER.debug("Alarm registers not available: %s", alarm_result)
            except ModbusException as err:
                if not self._alarm_registers_unavailable_logged:
                    _LOGGER.info(
                        "Alarm registers not supported on this device: %s", err
                    )
                    self._alarm_registers_unavailable_logged = True
                else:
                    _LOGGER.debug("Alarm registers not available on this device")

            on_time_seconds = (sensor_regs[1] << 16) | sensor_regs[2]

            session_active = holding_regs[0]
            if session_active and self._session_start_time is None:
                self._session_start_time = dt_util.utcnow()
                _LOGGER.debug("Session started at %s", self._session_start_time)
            elif not session_active:
                self._session_start_time = None

            remaining_time_minutes: int | None = None
            if session_active and self._session_start_time:
                elapsed_seconds = (
                    dt_util.utcnow() - self._session_start_time
                ).total_seconds()
                total_duration_seconds = holding_regs[2] * 60
                remaining_seconds = max(0, total_duration_seconds - elapsed_seconds)
                remaining_time_minutes = int(remaining_seconds // 60)

            data: dict[str, int | float | None] = {
                "session_active": holding_regs[0],
                "sauna_type": holding_regs[1],
                "sauna_duration": holding_regs[2],
                "fan_duration": holding_regs[3],
                "target_temperature": holding_regs[4],
                "fan_speed": holding_regs[5],
                "light": holding_regs[6],
                "current_temperature": sensor_regs[0],
                "on_time_seconds": on_time_seconds,
                "heater_status": sensor_regs[3],
                "door_status": sensor_regs[4],
                "remaining_time_minutes": remaining_time_minutes,
                "alarm_door_open": alarm_regs[0],
                "alarm_door_sensor": alarm_regs[1],
                "alarm_thermal_cutoff": alarm_regs[2],
                "alarm_internal_temp": alarm_regs[3],
                "alarm_temp_sensor_shorted": alarm_regs[4],
                "alarm_temp_sensor_not_connected": alarm_regs[5],
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
