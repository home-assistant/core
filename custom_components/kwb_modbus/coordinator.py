"""Coordinator for the KWB Modbus integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALWAYS_ACTIVE_MODULES,
    CONF_ADDON_MODULES,
    CONF_DISCOVERED_SENSORS,
    CONF_HEATING_DEVICE,
    CONF_SLAVE_ID,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    INDEXED_MODULES,
    SENSOR_STATUS_OK,
)
from .register_map import REGISTERS, SELECT_REGISTERS, VALUE_TABLES, RegisterDef

_LOGGER = logging.getLogger(__name__)


class KWBDataUpdateCoordinator(DataUpdateCoordinator[dict[int, Any]]):
    """Coordinator for KWB Heating Modbus data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncModbusTcpClient,
        entry: ConfigEntry,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self.slave_id = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
        self._heating_device: str = entry.data[CONF_HEATING_DEVICE]
        self._addon_modules: list[str] = entry.data.get(CONF_ADDON_MODULES, [])

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def get_all_module_keys(self) -> list[str]:
        """Return list of all active module keys (always-on + device + addons)."""
        return [*ALWAYS_ACTIVE_MODULES, self._heating_device, *self._addon_modules]

    def get_all_registers(self) -> list[RegisterDef]:
        """Return all value registers (no status registers) for active modules."""
        result: list[RegisterDef] = []
        for module_key in self.get_all_module_keys():
            result.extend(r for r in REGISTERS.get(module_key, []) if not r.is_status)
        return result

    def get_active_registers(self) -> list[RegisterDef]:
        """Return only registers that are enabled (should be polled)."""
        discovered: dict[str, bool] = self.entry.data.get(CONF_DISCOVERED_SENSORS, {})
        return [
            r for r in self.get_all_registers()
            if discovered.get(f"kwb_{r.address}", True)
        ]

    async def async_run_discovery(self) -> None:
        """Read status registers to determine which sensors are physically installed.

        Indexed module sensors (BUF/HC/DHWC/etc.) are enabled only when the
        corresponding status register returns SENSOR_STATUS_OK (2).
        Non-indexed sensors are always enabled.
        Saves result to config entry data.
        """
        _LOGGER.info("Starting KWB sensor discovery")
        discovered: dict[str, bool] = {}

        if not self.client.connected:
            await self.client.connect()

        for module_key in self.get_all_module_keys():
            for r in REGISTERS.get(module_key, []):
                if r.is_status:
                    continue

                uid = f"kwb_{r.address}"

                # Non-indexed sensors are always enabled
                if module_key not in INDEXED_MODULES or not r.index:
                    discovered[uid] = True
                    continue

                # Indexed sensors: check the status register (always address + 1)
                status_address = r.address + 1
                try:
                    result = await self.client.read_input_registers(
                        address=status_address,
                        count=1,
                        device_id=self.slave_id,
                    )
                    if result.isError():
                        _LOGGER.debug(
                            "Discovery: no response at %s for %s %s — disabling",
                            status_address, r.index, r.name,
                        )
                        discovered[uid] = False
                    else:
                        raw_status = result.registers[0]
                        is_ok = raw_status == SENSOR_STATUS_OK
                        discovered[uid] = is_ok
                        _LOGGER.debug(
                            "Discovery: %s %s → status=%s → enabled=%s",
                            r.index, r.name, raw_status, is_ok,
                        )
                except ModbusException as err:
                    _LOGGER.warning("Discovery read error at %s: %s", status_address, err)
                    discovered[uid] = False

        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_DISCOVERED_SENSORS: discovered},
        )
        _LOGGER.info(
            "Discovery complete: %d enabled, %d disabled",
            sum(1 for v in discovered.values() if v),
            sum(1 for v in discovered.values() if not v),
        )

    def get_all_select_registers(self) -> list:
        """Return all select registers for active modules."""
        result = []
        for module_key in self.get_all_module_keys():
            result.extend(SELECT_REGISTERS.get(module_key, []))
        return result

    async def async_read_holding_register(self, address: int) -> int | None:
        """Read a single holding register (func 03)."""
        if not self.client.connected:
            await self.client.connect()
        try:
            result = await self.client.read_holding_registers(
                address=address, count=1, device_id=self.slave_id
            )
        except ModbusException as err:
            _LOGGER.warning("Error reading holding register %s: %s", address, err)
            return None
        if result.isError():
            return None
        return result.registers[0]

    async def async_write_holding_register(self, address: int, value: int) -> bool:
        """Write a single holding register (func 06)."""
        if not self.client.connected:
            await self.client.connect()
        try:
            result = await self.client.write_register(
                address=address, value=value, device_id=self.slave_id
            )
        except ModbusException as err:
            _LOGGER.error("Exception writing holding register %s: %s", address, err)
            return False
        if result.isError():
            _LOGGER.error("Error writing holding register %s = %s", address, value)
            return False
        _LOGGER.debug("Wrote holding register %s = %s", address, value)
        return True

    async def _async_update_data(self) -> dict[int, Any]:
        """Fetch data for all enabled registers. Returns {address: value}."""
        if not self.client.connected:
            try:
                await self.client.connect()
            except ModbusException as err:
                raise UpdateFailed(f"Cannot connect to KWB device: {err}") from err

        active = sorted(self.get_active_registers(), key=lambda r: r.address)
        if not active:
            return {}

        # Build batches of consecutive addresses (max gap 10, max 125 registers)
        batches: list[tuple[int, int]] = []
        batch_start = active[0].address
        batch_end = active[0].address + active[0].count

        for r in active[1:]:
            if r.address <= batch_end + 10 and (r.address + r.count - batch_start) <= 125:
                batch_end = max(batch_end, r.address + r.count)
            else:
                batches.append((batch_start, batch_end - batch_start))
                batch_start = r.address
                batch_end = r.address + r.count
        batches.append((batch_start, batch_end - batch_start))

        # Read batches
        raw_data: dict[int, int] = {}
        for batch_addr, batch_count in batches:
            try:
                result = await self.client.read_input_registers(
                    address=batch_addr,
                    count=batch_count,
                    device_id=self.slave_id,
                )
                if result.isError():
                    _LOGGER.warning("Modbus error at %s count=%s", batch_addr, batch_count)
                    continue
                for i, val in enumerate(result.registers):
                    raw_data[batch_addr + i] = val
            except ModbusException as err:
                raise UpdateFailed(f"Modbus read failed: {err}") from err

        # Process raw → scaled values
        processed: dict[int, Any] = {}
        for r in active:
            raw = raw_data.get(r.address)
            if raw is None:
                processed[r.address] = None
                continue

            if r.data_type == "s16" and raw > 32767:
                raw = raw - 65536

            if r.count == 2:
                raw2 = raw_data.get(r.address + 1, 0)
                raw = (raw << 16) | raw2
                if r.data_type == "s32" and raw > 2147483647:
                    raw = raw - 4294967296

            value: Any = raw * r.scale if r.scale != 1.0 else raw

            if r.value_table and r.value_table in VALUE_TABLES:
                value = VALUE_TABLES[r.value_table].get(int(raw), str(raw))

            processed[r.address] = value

        return processed
