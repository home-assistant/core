"""Coordinator for Vevor Diesel Heater."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    StatisticData,
    StatisticMetaData,
    StatisticMeanType,
)
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ABBA_NOTIFY_UUID,
    ABBA_SERVICE_UUID,
    ABBA_WRITE_UUID,
    AUTO_OFFSET_THRESHOLD,
    AUTO_OFFSET_THROTTLE_SECONDS,
    CHARACTERISTIC_UUID,
    CHARACTERISTIC_UUID_ALT,
    CONF_AUTO_OFFSET_ENABLED,
    CONF_AUTO_OFFSET_MAX,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_PIN,
    CONF_TEMPERATURE_OFFSET,
    DEFAULT_AUTO_OFFSET_MAX,
    DEFAULT_PIN,
    DEFAULT_TEMPERATURE_OFFSET,
    DOMAIN,
    FUEL_CONSUMPTION_TABLE,
    MAX_HEATER_OFFSET,
    MAX_HISTORY_DAYS,
    MIN_HEATER_OFFSET,
    PROTOCOL_HEADER_ABBA,
    PROTOCOL_HEADER_CBFF,
    PROTOCOL_HEADER_AA77,
    RUNNING_STEP_RUNNING,
    SENSOR_TEMP_MAX,
    SENSOR_TEMP_MIN,
    SERVICE_UUID,
    SERVICE_UUID_ALT,
    STORAGE_KEY_AUTO_OFFSET_ENABLED,
    STORAGE_KEY_FUEL_SINCE_RESET,
    STORAGE_KEY_LAST_REFUELED,
    STORAGE_KEY_TANK_CAPACITY,
    STORAGE_KEY_DAILY_DATE,
    STORAGE_KEY_DAILY_FUEL,
    STORAGE_KEY_DAILY_HISTORY,
    STORAGE_KEY_DAILY_RUNTIME,
    STORAGE_KEY_DAILY_RUNTIME_DATE,
    STORAGE_KEY_DAILY_RUNTIME_HISTORY,
    STORAGE_KEY_TOTAL_FUEL,
    STORAGE_KEY_TOTAL_RUNTIME,
    UPDATE_INTERVAL,
)
from diesel_heater_ble import (
    HeaterProtocol,
    ProtocolAA55,
    ProtocolAA55Encrypted,
    ProtocolAA66,
    ProtocolAA66Encrypted,
    ProtocolABBA,
    ProtocolCBFF,
    _decrypt_data,
    _u8_to_number,
)

_LOGGER = logging.getLogger(__name__)


class _HeaterLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that prefixes messages with heater ID."""

    def process(self, msg, kwargs):
        return f"[{self.extra['heater_id']}] {msg}", kwargs


class VevorHeaterCoordinator(DataUpdateCoordinator):
    """Vevor Heater coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: bluetooth.BleakDevice,
        config_entry: Any,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.address = ble_device.address
        self._ble_device = ble_device
        self.config_entry = config_entry
        # Per-instance logger with heater ID prefix for multi-heater support
        self._logger = _HeaterLoggerAdapter(
            _LOGGER, {"heater_id": ble_device.address[-5:]}
        )
        self._client: BleakClient | None = None
        self._characteristic = None
        self._active_char_uuid: str | None = None  # Track which UUID variant is active
        self._notification_data: bytearray | None = None
        # Get passkey from config, default to 1234 (factory default for most heaters)
        self._passkey = config_entry.data.get(CONF_PIN, DEFAULT_PIN)
        self._protocol_mode = 0  # Will be detected from response (1-6)
        self._protocol: HeaterProtocol | None = None  # Active protocol handler
        cbff = ProtocolCBFF()
        # CBFF encryption uses BLE MAC (without colons, uppercased) as key2
        device_sn = ble_device.address.replace(":", "").replace("-", "").upper()
        cbff.set_device_sn(device_sn)

        self._protocols: dict[int, HeaterProtocol] = {
            1: ProtocolAA55(),
            2: ProtocolAA55Encrypted(),
            3: ProtocolAA66(),
            4: ProtocolAA66Encrypted(),
            5: ProtocolABBA(),
            6: cbff,
        }
        self._is_abba_device = False  # True if using ABBA/HeaterCC protocol
        self._abba_write_char = None  # ABBA devices use separate write characteristic
        self._connection_attempts = 0
        self._last_connection_attempt = 0.0
        self._consecutive_failures = 0  # Track consecutive update failures
        self._max_stale_cycles = 3  # Keep last values for this many failed cycles
        self._last_valid_data: dict[str, Any] = {}  # Cache of last valid sensor readings
        self._heater_uses_fahrenheit: bool = False  # Detected from heater response
        
        # Current state
        self.data: dict[str, Any] = {
            "running_state": None,
            "error_code": None,
            "running_step": None,
            "altitude": None,
            "running_mode": None,
            "set_level": None,
            "set_temp": None,
            "supply_voltage": None,
            "case_temperature": None,
            "cab_temperature": None,
            "cab_temperature_raw": None,  # Raw temperature before any offset
            "heater_offset": 0,  # Current offset sent to heater (cmd 20)
            "connected": False,
            "auto_start_stop": None,  # Automatic Start/Stop flag (byte 31)
            "auto_offset_enabled": False,  # Auto offset adjustment enabled
            # Configuration settings (bytes 26-30)
            "language": None,  # byte 26: Voice notification language
            "temp_unit": None,  # byte 27: 0=Celsius, 1=Fahrenheit
            "tank_volume": None,  # byte 28: Tank volume in liters
            "pump_type": None,  # byte 29: Oil pump type
            "altitude_unit": None,  # byte 30: 0=Meters, 1=Feet
            "rf433_enabled": None,  # byte 29 value 20/21 indicates RF433 status
            # Fuel consumption tracking
            "hourly_fuel_consumption": None,
            "daily_fuel_consumed": 0.0,
            "total_fuel_consumed": 0.0,
            # Runtime tracking
            "daily_runtime_hours": 0.0,
            "total_runtime_hours": 0.0,
            # Fuel level tracking
            "tank_capacity": None,  # User-defined tank capacity in liters (1-100)
            "fuel_remaining": None,
            "fuel_consumed_since_reset": 0.0,
            "last_refueled": None,  # ISO timestamp of last refuel reset
        }

        # Fuel consumption tracking (minimal)
        self._store = Store(hass, 1, f"{DOMAIN}_{ble_device.address}")
        self._last_update_time: float = time.time()
        self._total_fuel_consumed: float = 0.0
        self._daily_fuel_consumed: float = 0.0
        self._daily_fuel_history: dict[str, float] = {}  # date -> liters consumed
        self._fuel_consumed_since_reset: float = 0.0  # Fuel since last refuel reset
        self._last_save_time: float = time.time()
        self._last_reset_date: str = datetime.now().date().isoformat()

        # Runtime tracking
        self._total_runtime_seconds: float = 0.0
        self._daily_runtime_seconds: float = 0.0
        self._daily_runtime_history: dict[str, float] = {}  # date -> hours running
        self._last_runtime_reset_date: str = datetime.now().date().isoformat()

        # Auto temperature offset from external sensor
        self._auto_offset_unsub: callable | None = None
        self._last_auto_offset_time: float = 0.0
        self._current_heater_offset: int = 0  # Current offset sent to heater via cmd 12

    @property
    def protocol_mode(self) -> int:
        """Return the detected BLE protocol mode (0=unknown, 1-6=detected)."""
        return self._protocol_mode

    async def async_load_data(self) -> None:
        """Load persistent fuel consumption and runtime data."""
        try:
            data = await self._store.async_load()
            if data:
                # Load fuel consumption data
                self._total_fuel_consumed = data.get(STORAGE_KEY_TOTAL_FUEL, 0.0)
                self._daily_fuel_consumed = data.get(STORAGE_KEY_DAILY_FUEL, 0.0)
                self._daily_fuel_history = data.get(STORAGE_KEY_DAILY_HISTORY, {})

                # Load runtime tracking data
                self._total_runtime_seconds = data.get(STORAGE_KEY_TOTAL_RUNTIME, 0.0)
                self._daily_runtime_seconds = data.get(STORAGE_KEY_DAILY_RUNTIME, 0.0)
                self._daily_runtime_history = data.get(STORAGE_KEY_DAILY_RUNTIME_HISTORY, {})

                # Clean old history entries (keep only last MAX_HISTORY_DAYS)
                self._clean_old_history()
                self._clean_old_runtime_history()

                # Check if we need to reset daily fuel counter
                saved_date = data.get(STORAGE_KEY_DAILY_DATE)
                if saved_date:
                    today = datetime.now().date().isoformat()
                    if saved_date != today:
                        self._logger.info("New day detected at startup, resetting daily fuel counter")
                        # Save yesterday's consumption to history before resetting
                        if self._daily_fuel_consumed > 0:
                            self._daily_fuel_history[saved_date] = round(self._daily_fuel_consumed, 2)
                            self._logger.info("Saved %s: %.2fL to history", saved_date, self._daily_fuel_consumed)
                        self._daily_fuel_consumed = 0.0
                        self._last_reset_date = today
                    else:
                        self._last_reset_date = saved_date
                else:
                    # No saved date, use today
                    self._last_reset_date = datetime.now().date().isoformat()

                # Check if we need to reset daily runtime counter
                saved_runtime_date = data.get(STORAGE_KEY_DAILY_RUNTIME_DATE)
                if saved_runtime_date:
                    today = datetime.now().date().isoformat()
                    if saved_runtime_date != today:
                        self._logger.info("New day detected at startup, resetting daily runtime counter")
                        # Save yesterday's runtime to history before resetting
                        if self._daily_runtime_seconds > 0:
                            hours = round(self._daily_runtime_seconds / 3600.0, 2)
                            self._daily_runtime_history[saved_runtime_date] = hours
                            self._logger.info("Saved %s: %.2fh to runtime history", saved_runtime_date, hours)
                        self._daily_runtime_seconds = 0.0
                        self._last_runtime_reset_date = today
                    else:
                        self._last_runtime_reset_date = saved_runtime_date
                else:
                    # No saved date, use today
                    self._last_runtime_reset_date = datetime.now().date().isoformat()

                # Update data dictionary with loaded values
                self.data["total_fuel_consumed"] = round(self._total_fuel_consumed, 2)
                self.data["daily_fuel_consumed"] = round(self._daily_fuel_consumed, 2)
                self.data["daily_fuel_history"] = self._daily_fuel_history
                self.data["daily_runtime_hours"] = round(self._daily_runtime_seconds / 3600.0, 2)
                self.data["total_runtime_hours"] = round(self._total_runtime_seconds / 3600.0, 2)
                self.data["daily_runtime_history"] = self._daily_runtime_history

                self._logger.debug(
                    "Loaded fuel data: total=%.2fL, daily=%.2fL, history entries=%d",
                    self._total_fuel_consumed,
                    self._daily_fuel_consumed,
                    len(self._daily_fuel_history)
                )
                self._logger.debug(
                    "Loaded runtime data: total=%.2fh, daily=%.2fh, history entries=%d",
                    self._total_runtime_seconds / 3600.0,
                    self._daily_runtime_seconds / 3600.0,
                    len(self._daily_runtime_history)
                )

                # Load fuel level tracking
                self._fuel_consumed_since_reset = data.get(STORAGE_KEY_FUEL_SINCE_RESET, 0.0)
                self.data["fuel_consumed_since_reset"] = round(self._fuel_consumed_since_reset, 2)
                tank_capacity = data.get(STORAGE_KEY_TANK_CAPACITY)
                if tank_capacity is not None:
                    self.data["tank_capacity"] = tank_capacity
                last_refueled = data.get(STORAGE_KEY_LAST_REFUELED)
                if last_refueled is not None:
                    self.data["last_refueled"] = last_refueled
                self._update_fuel_remaining()
                self._logger.debug(
                    "Loaded fuel level data: consumed_since_reset=%.2fL, tank_capacity=%s, last_refueled=%s",
                    self._fuel_consumed_since_reset, self.data.get("tank_capacity"), self.data.get("last_refueled")
                )

                # Load auto offset enabled state
                auto_offset_enabled = data.get(STORAGE_KEY_AUTO_OFFSET_ENABLED, False)
                self.data["auto_offset_enabled"] = auto_offset_enabled
                self._logger.debug("Loaded auto_offset_enabled: %s", auto_offset_enabled)

                # Import existing history into statistics for native graphing
                await self._import_all_history_statistics()
                await self._import_all_runtime_history_statistics()
        except Exception as err:
            self._logger.warning("Could not load data: %s", err)

        # Set up external temperature sensor listener for auto offset
        await self._setup_external_temp_listener()

    async def _setup_external_temp_listener(self) -> None:
        """Set up listener for external temperature sensor state changes."""
        # Clean up any existing listener
        if self._auto_offset_unsub:
            self._auto_offset_unsub()
            self._auto_offset_unsub = None

        # Get external sensor entity_id from config
        external_sensor = self.config_entry.data.get(CONF_EXTERNAL_TEMP_SENSOR, "")
        if not external_sensor:
            self._logger.debug("No external temperature sensor configured")
            return

        self._logger.info(
            "Setting up auto offset from external sensor: %s (max offset: %d°C)",
            external_sensor,
            self.config_entry.data.get(CONF_AUTO_OFFSET_MAX, DEFAULT_AUTO_OFFSET_MAX)
        )

        # Subscribe to state changes
        self._auto_offset_unsub = async_track_state_change_event(
            self.hass,
            [external_sensor],
            self._async_external_temp_changed
        )

        # Calculate initial offset
        await self._async_calculate_auto_offset()

    @callback
    def _async_external_temp_changed(self, event) -> None:
        """Handle external temperature sensor state changes."""
        # Schedule the async calculation
        self.hass.async_create_task(self._async_calculate_auto_offset())

    async def _async_calculate_auto_offset(self) -> None:
        """Calculate and apply auto temperature offset based on external sensor.

        This compares the heater's internal temperature sensor with an external
        reference sensor and calculates an offset to compensate for any difference.
        The offset is sent to the heater via BLE command 12, so the heater itself
        uses the corrected temperature for auto-start/stop logic.

        The offset is limited by CONF_AUTO_OFFSET_MAX and throttled to avoid
        frequent BLE commands.
        """
        # Check if auto offset is enabled
        if not self.data.get("auto_offset_enabled", False):
            self._logger.debug("Auto offset disabled")
            return

        external_sensor = self.config_entry.data.get(CONF_EXTERNAL_TEMP_SENSOR, "")
        if not external_sensor:
            self._logger.debug("No external temperature sensor configured")
            return

        # Throttle offset updates to avoid too many BLE commands
        current_time = time.time()
        if current_time - self._last_auto_offset_time < AUTO_OFFSET_THROTTLE_SECONDS:
            self._logger.debug("Auto offset throttled (last update %.0fs ago)",
                         current_time - self._last_auto_offset_time)
            return

        # Get external sensor state
        state = self.hass.states.get(external_sensor)
        if state is None or state.state in ("unknown", "unavailable"):
            self._logger.debug("External sensor %s unavailable", external_sensor)
            return

        try:
            external_temp = float(state.state)
        except (ValueError, TypeError):
            self._logger.warning("Invalid external sensor value: %s", state.state)
            return

        # Check if external sensor uses Fahrenheit and convert to Celsius
        # The heater offset calculation must be done in Celsius
        unit = state.attributes.get("unit_of_measurement", "")
        if unit in ("°F", "℉", "F"):
            # Convert Fahrenheit to Celsius: C = (F - 32) * 5/9
            external_temp_celsius = (external_temp - 32) * 5 / 9
            self._logger.debug(
                "External sensor in Fahrenheit: %.1f°F → %.1f°C",
                external_temp, external_temp_celsius
            )
            external_temp = external_temp_celsius

        # Get heater's raw cab temperature (before any offset)
        raw_heater_temp = self.data.get("cab_temperature_raw")
        if raw_heater_temp is None:
            self._logger.debug("Heater raw temperature not available yet")
            return

        # Round external temp to nearest integer (heater only accepts integer offset)
        external_temp_rounded = round(external_temp)

        # Calculate the difference: positive offset means heater reads lower than external
        # If external=22°C and heater=25°C, we need offset=-3 to make heater think it's 22°C
        difference = external_temp_rounded - raw_heater_temp

        # Only adjust if difference is significant (>= 1°C)
        if abs(difference) < AUTO_OFFSET_THRESHOLD:
            self._logger.debug(
                "Auto offset: difference (%.1f°C) below threshold (%.1f°C), no adjustment",
                difference, AUTO_OFFSET_THRESHOLD
            )
            return

        # Calculate new offset (clamped to -max to +max range)
        # Both positive and negative offsets now work via BLE
        max_offset = self.config_entry.data.get(CONF_AUTO_OFFSET_MAX, DEFAULT_AUTO_OFFSET_MAX)
        max_offset = min(max_offset, MAX_HEATER_OFFSET)  # Cap at 10
        new_offset = int(max(-max_offset, min(max_offset, difference)))

        # Only send command if offset changed
        if new_offset != self._current_heater_offset:
            old_offset = self._current_heater_offset
            self._last_auto_offset_time = current_time

            self._logger.info(
                "Auto offset: external=%.1f°C (rounded=%d), heater_raw=%.1f°C, "
                "difference=%.1f°C, sending offset: %d → +%d°C",
                external_temp, external_temp_rounded, raw_heater_temp,
                difference, old_offset, new_offset
            )

            # Send the offset command to the heater
            await self.async_set_heater_offset(new_offset)

    async def async_save_data(self) -> None:
        """Save persistent fuel consumption, runtime data, and settings."""
        try:
            data = {
                # Fuel data
                STORAGE_KEY_TOTAL_FUEL: self._total_fuel_consumed,
                STORAGE_KEY_DAILY_FUEL: self._daily_fuel_consumed,
                STORAGE_KEY_DAILY_DATE: datetime.now().date().isoformat(),
                STORAGE_KEY_DAILY_HISTORY: self._daily_fuel_history,
                # Runtime data
                STORAGE_KEY_TOTAL_RUNTIME: self._total_runtime_seconds,
                STORAGE_KEY_DAILY_RUNTIME: self._daily_runtime_seconds,
                STORAGE_KEY_DAILY_RUNTIME_DATE: datetime.now().date().isoformat(),
                STORAGE_KEY_DAILY_RUNTIME_HISTORY: self._daily_runtime_history,
                # Fuel level tracking
                STORAGE_KEY_FUEL_SINCE_RESET: self._fuel_consumed_since_reset,
                STORAGE_KEY_TANK_CAPACITY: self.data.get("tank_capacity"),
                STORAGE_KEY_LAST_REFUELED: self.data.get("last_refueled"),
                # Settings
                STORAGE_KEY_AUTO_OFFSET_ENABLED: self.data.get("auto_offset_enabled", False),
            }
            await self._store.async_save(data)
            self._logger.debug(
                "Saved data: fuel history=%d entries, runtime history=%d entries, auto_offset=%s",
                len(self._daily_fuel_history),
                len(self._daily_runtime_history),
                self.data.get("auto_offset_enabled", False)
            )
        except Exception as err:
            self._logger.warning("Could not save data: %s", err)

    def _clean_old_history(self) -> None:
        """Remove history entries older than MAX_HISTORY_DAYS."""
        if not self._daily_fuel_history:
            return

        cutoff_date = (datetime.now().date() - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
        old_keys = [date for date in self._daily_fuel_history if date < cutoff_date]

        for date in old_keys:
            del self._daily_fuel_history[date]

        if old_keys:
            self._logger.debug("Removed %d old fuel history entries (before %s)", len(old_keys), cutoff_date)

    def _clean_old_runtime_history(self) -> None:
        """Remove runtime history entries older than MAX_HISTORY_DAYS."""
        if not self._daily_runtime_history:
            return

        cutoff_date = (datetime.now().date() - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
        old_keys = [date for date in self._daily_runtime_history if date < cutoff_date]

        for date in old_keys:
            del self._daily_runtime_history[date]

        if old_keys:
            self._logger.debug("Removed %d old runtime history entries (before %s)", len(old_keys), cutoff_date)

    async def _import_statistics(self, date_str: str, liters: float) -> None:
        """Import daily fuel consumption into Home Assistant statistics for graphing."""
        # Skip if recorder is not available
        if not (recorder := get_instance(self.hass)):
            self._logger.debug("Recorder not available, skipping statistics import")
            return

        # Define statistic metadata
        # statistic_id must be unique per device and lowercase with valid characters
        device_id = self.address.replace(":", "_").lower()
        statistic_id = f"{DOMAIN}:{device_id}_daily_fuel_consumed"
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=f"Daily Fuel Consumption ({self.address[-5:]})",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.LITERS,
            unit_class="volume",
        )

        # Parse date and create timestamp at midnight (start of hour required by HA)
        try:
            date_obj = datetime.fromisoformat(date_str)
            # Use midnight (00:00:00) - HA requires timestamps at top of hour
            midnight = datetime.combine(date_obj.date(), datetime.min.time())
            # Make it timezone-aware
            timestamp = dt_util.as_utc(midnight)
        except (ValueError, TypeError) as err:
            self._logger.error("Failed to parse date %s: %s", date_str, err)
            return

        # Create statistic data point
        statistic = StatisticData(
            start=timestamp,
            state=liters,
            sum=liters,  # Sum for this day
        )

        # Import the statistic (wrapped in try-except to prevent crashes)
        # Use async_add_external_statistics for external statistics (uses : delimiter)
        self._logger.info(
            "Importing fuel statistic: id=%s, date=%s, value=%.2fL",
            statistic_id, date_str, liters
        )
        try:
            async_add_external_statistics(self.hass, metadata, [statistic])
            self._logger.debug("Successfully imported fuel statistic for %s", date_str)
        except Exception as err:
            self._logger.warning(
                "Could not import fuel statistic for %s: %s (statistic_id=%s)",
                date_str, err, statistic_id
            )

    async def _import_all_history_statistics(self) -> None:
        """Import all existing history data into statistics (called at startup)."""
        if not self._daily_fuel_history:
            self._logger.debug("No history to import into statistics")
            return

        self._logger.info("Importing %d days of fuel history into statistics", len(self._daily_fuel_history))

        for date_str, liters in sorted(self._daily_fuel_history.items()):
            await self._import_statistics(date_str, liters)

        self._logger.info("Completed import of fuel history into statistics")

    async def _import_runtime_statistics(self, date_str: str, hours: float) -> None:
        """Import daily runtime into Home Assistant statistics for graphing."""
        # Skip if recorder is not available
        if not (recorder := get_instance(self.hass)):
            self._logger.debug("Recorder not available, skipping runtime statistics import")
            return

        # Define statistic metadata
        # statistic_id must be unique per device and lowercase with valid characters
        device_id = self.address.replace(":", "_").lower()
        statistic_id = f"{DOMAIN}:{device_id}_daily_runtime_hours"
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=f"Daily Runtime ({self.address[-5:]})",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfTime.HOURS,
            unit_class="duration",
        )

        # Parse date and create timestamp at midnight (start of hour required by HA)
        try:
            date_obj = datetime.fromisoformat(date_str)
            # Use midnight (00:00:00) - HA requires timestamps at top of hour
            midnight = datetime.combine(date_obj.date(), datetime.min.time())
            # Make it timezone-aware
            timestamp = dt_util.as_utc(midnight)
        except (ValueError, TypeError) as err:
            self._logger.error("Failed to parse date %s: %s", date_str, err)
            return

        # Create statistic data point
        statistic = StatisticData(
            start=timestamp,
            state=hours,
            sum=hours,  # Sum for this day
        )

        # Import the statistic (wrapped in try-except to prevent crashes)
        # Use async_add_external_statistics for external statistics (uses : delimiter)
        self._logger.info(
            "Importing runtime statistic: id=%s, date=%s, value=%.2fh",
            statistic_id, date_str, hours
        )
        try:
            async_add_external_statistics(self.hass, metadata, [statistic])
            self._logger.debug("Successfully imported runtime statistic for %s", date_str)
        except Exception as err:
            self._logger.warning(
                "Could not import runtime statistic for %s: %s (statistic_id=%s)",
                date_str, err, statistic_id
            )

    async def _import_all_runtime_history_statistics(self) -> None:
        """Import all existing runtime history data into statistics (called at startup)."""
        if not self._daily_runtime_history:
            self._logger.debug("No runtime history to import into statistics")
            return

        self._logger.info("Importing %d days of runtime history into statistics", len(self._daily_runtime_history))

        for date_str, hours in sorted(self._daily_runtime_history.items()):
            await self._import_runtime_statistics(date_str, hours)

        self._logger.info("Completed import of runtime history into statistics")

    def _calculate_fuel_consumption(self, elapsed_seconds: float) -> float:
        """Calculate fuel consumed based on power level and elapsed time.
        
        Returns fuel consumed in liters.
        """
        # Only consume fuel when actually running
        if self.data.get("running_step") != RUNNING_STEP_RUNNING:
            return 0.0
            
        power_level = self.data.get("set_level", 1)
        consumption_rate = FUEL_CONSUMPTION_TABLE.get(power_level, 0.16)  # L/h
        
        # Calculate fuel consumed in this interval
        hours_elapsed = elapsed_seconds / 3600.0
        fuel_consumed = consumption_rate * hours_elapsed
        
        return fuel_consumed

    def _update_fuel_tracking(self, elapsed_seconds: float) -> None:
        """Update fuel consumption tracking."""
        fuel_consumed = self._calculate_fuel_consumption(elapsed_seconds)

        if fuel_consumed > 0:
            self._total_fuel_consumed += fuel_consumed
            self._daily_fuel_consumed += fuel_consumed
            self._fuel_consumed_since_reset += fuel_consumed

        # Calculate instantaneous consumption rate
        power_level = self.data.get("set_level", 1)
        if self.data.get("running_step") == RUNNING_STEP_RUNNING:
            hourly_consumption = FUEL_CONSUMPTION_TABLE.get(power_level, 0.16)
        else:
            hourly_consumption = 0.0

        # Update data dictionary
        self.data["hourly_fuel_consumption"] = round(hourly_consumption, 2)
        self.data["daily_fuel_consumed"] = round(self._daily_fuel_consumed, 2)
        self.data["total_fuel_consumed"] = round(self._total_fuel_consumed, 2)
        self.data["fuel_consumed_since_reset"] = round(self._fuel_consumed_since_reset, 2)
        self._update_fuel_remaining()

    def _update_fuel_remaining(self) -> None:
        """Update estimated fuel remaining based on tank capacity and consumption since reset."""
        tank_capacity = self.data.get("tank_capacity")
        if tank_capacity is None or tank_capacity <= 0:
            # Tank capacity not set — can't estimate
            self.data["fuel_remaining"] = None
            return

        remaining = tank_capacity - self._fuel_consumed_since_reset
        self.data["fuel_remaining"] = round(max(0.0, remaining), 2)

    async def async_reset_fuel_level(self) -> None:
        """Reset fuel level tracking (called when user refuels)."""
        self._fuel_consumed_since_reset = 0.0
        self.data["fuel_consumed_since_reset"] = 0.0
        self.data["last_refueled"] = dt_util.now().isoformat()
        self._update_fuel_remaining()
        await self.async_save_data()
        self._logger.info("⛽ Fuel level reset (tank refueled at %s)", self.data["last_refueled"])
        self.async_set_updated_data(self.data)

    async def async_set_tank_capacity(self, capacity: int) -> None:
        """Set the user-defined tank capacity in liters (1-100)."""
        capacity = max(1, min(100, capacity))
        self.data["tank_capacity"] = capacity
        self._update_fuel_remaining()
        await self.async_save_data()
        self._logger.info("⛽ Tank capacity set to %dL", capacity)
        self.async_set_updated_data(self.data)

    def _update_runtime_tracking(self, elapsed_seconds: float) -> None:
        """Update runtime tracking."""
        # Only count runtime when heater is actually running
        if self.data.get("running_step") == RUNNING_STEP_RUNNING:
            self._total_runtime_seconds += elapsed_seconds
            self._daily_runtime_seconds += elapsed_seconds

        # Update data dictionary (convert to hours for display)
        self.data["daily_runtime_hours"] = round(self._daily_runtime_seconds / 3600.0, 2)
        self.data["total_runtime_hours"] = round(self._total_runtime_seconds / 3600.0, 2)

    async def _check_daily_reset(self) -> None:
        """Check if we need to reset daily fuel counter (runs every update, even if offline)."""
        current_date = datetime.now().date().isoformat()
        if current_date != self._last_reset_date:
            # Save yesterday's consumption to history before resetting
            if self._daily_fuel_consumed > 0:
                liters_consumed = round(self._daily_fuel_consumed, 2)
                self._daily_fuel_history[self._last_reset_date] = liters_consumed
                self._logger.info(
                    "New day detected: saved %s consumption (%.2fL) to history",
                    self._last_reset_date,
                    liters_consumed
                )

                # Import into statistics for native graphing
                await self._import_statistics(self._last_reset_date, liters_consumed)

            self._logger.info(
                "Resetting daily fuel counter from %.2fL to 0.0L (was %s, now %s)",
                self._daily_fuel_consumed,
                self._last_reset_date,
                current_date
            )

            self._daily_fuel_consumed = 0.0
            self._last_reset_date = current_date
            self.data["daily_fuel_consumed"] = 0.0

            # Clean old history and update data
            self._clean_old_history()
            self.data["daily_fuel_history"] = self._daily_fuel_history

            # Save immediately after reset to persist the new day and history
            await self.async_save_data()

    async def _check_daily_runtime_reset(self) -> None:
        """Check if we need to reset daily runtime counter (runs every update, even if offline)."""
        current_date = datetime.now().date().isoformat()
        if current_date != self._last_runtime_reset_date:
            # Save yesterday's runtime to history before resetting
            if self._daily_runtime_seconds > 0:
                hours_running = round(self._daily_runtime_seconds / 3600.0, 2)
                self._daily_runtime_history[self._last_runtime_reset_date] = hours_running
                self._logger.info(
                    "New day detected: saved %s runtime (%.2fh) to history",
                    self._last_runtime_reset_date,
                    hours_running
                )

                # Import into statistics for native graphing
                await self._import_runtime_statistics(self._last_runtime_reset_date, hours_running)

            self._logger.info(
                "Resetting daily runtime counter from %.2fh to 0.0h (was %s, now %s)",
                self._daily_runtime_seconds / 3600.0,
                self._last_runtime_reset_date,
                current_date
            )

            self._daily_runtime_seconds = 0.0
            self._last_runtime_reset_date = current_date
            self.data["daily_runtime_hours"] = 0.0

            # Clean old history and update data
            self._clean_old_runtime_history()
            self.data["daily_runtime_history"] = self._daily_runtime_history

            # Save immediately after reset to persist the new day and history
            await self.async_save_data()

    # Fields that represent volatile heater state (cleared on disconnect)
    _VOLATILE_FIELDS = (
        "case_temperature", "cab_temperature", "cab_temperature_raw",
        "supply_voltage", "running_state", "running_step", "running_mode",
        "set_level", "set_temp", "altitude", "error_code",
        "hourly_fuel_consumption", "co_ppm", "remain_run_time",
    )

    def _clear_sensor_values(self) -> None:
        """Clear volatile sensor values to show as unavailable."""
        for key in self._VOLATILE_FIELDS:
            self.data[key] = None

    def _restore_stale_data(self) -> None:
        """Restore last valid sensor values during temporary connection issues."""
        if self._last_valid_data:
            for key in self._VOLATILE_FIELDS:
                if key in self._last_valid_data:
                    self.data[key] = self._last_valid_data[key]

    def _save_valid_data(self) -> None:
        """Save current sensor values as last valid data."""
        self._last_valid_data = {
            key: self.data.get(key) for key in self._VOLATILE_FIELDS
        }

    def _handle_connection_failure(self, err: Exception) -> None:
        """Handle connection failure with stale data tolerance."""
        self._consecutive_failures += 1

        if self._consecutive_failures <= self._max_stale_cycles:
            # Keep last valid values and stay "connected" during tolerance window
            self._restore_stale_data()
            self._logger.debug(
                "Update failed (attempt %d/%d), keeping last values: %s",
                self._consecutive_failures,
                self._max_stale_cycles,
                err
            )
        else:
            # Too many failures, mark disconnected and clear values
            self.data["connected"] = False
            self._clear_sensor_values()
            if self._consecutive_failures == self._max_stale_cycles + 1:
                self._logger.warning(
                    "Vevor Heater offline after %d attempts: %s",
                    self._consecutive_failures,
                    err
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from the heater."""
        # Check for daily reset FIRST, even if heater is offline
        # This ensures the daily counters reset at midnight regardless of connection status
        await self._check_daily_reset()
        await self._check_daily_runtime_reset()

        if not self._client or not self._client.is_connected:
            try:
                await self._ensure_connected()
            except Exception as err:
                self._handle_connection_failure(err)
                raise UpdateFailed(f"Failed to connect: {err}")

        try:
            # Request status with retries (up to 3 attempts)
            max_retries = 3
            status = False
            for attempt in range(max_retries):
                status = await self._send_command(1, 0)
                if status:
                    break
                if attempt < max_retries - 1:
                    self._logger.debug(
                        "Status request timed out (attempt %d/%d), retrying...",
                        attempt + 1, max_retries
                    )
                    await asyncio.sleep(1.0)

            if status:
                self.data["connected"] = True
                # Reset failure counter and save valid data on success
                self._consecutive_failures = 0
                self._save_valid_data()

                # Update fuel consumption and runtime tracking
                current_time = time.time()
                elapsed_seconds = current_time - self._last_update_time
                self._last_update_time = current_time

                self._update_fuel_tracking(elapsed_seconds)
                self._update_runtime_tracking(elapsed_seconds)

                # Save data periodically (every 5 minutes)
                if current_time - self._last_save_time >= 300:
                    await self.async_save_data()
                    self._last_save_time = current_time

                return self.data
            else:
                self._handle_connection_failure(Exception("No status received"))
                # During stale tolerance window, return stale data instead of
                # raising UpdateFailed — keeps entities available
                if self._consecutive_failures <= self._max_stale_cycles:
                    return self.data
                raise UpdateFailed("No status received from heater")

        except UpdateFailed:
            raise
        except Exception as err:
            self._logger.debug("Error updating data: %s", err)
            self._handle_connection_failure(err)
            if self._consecutive_failures <= self._max_stale_cycles:
                return self.data
            raise UpdateFailed(f"Error updating data: {err}")

    async def _ensure_connected(self) -> None:
        """Ensure BLE connection is established with exponential backoff."""
        # Check if already connected
        if self._client and self._client.is_connected:
            self._connection_attempts = 0  # Reset on successful connection
            return

        # Clean up any stale client before attempting new connection
        await self._cleanup_connection()

        # Exponential backoff: 5s, 10s, 20s, 40s
        current_time = time.time()
        if self._connection_attempts > 0:
            backoff_delays = [5, 10, 20, 40]
            delay_index = min(self._connection_attempts - 1, len(backoff_delays) - 1)
            required_delay = backoff_delays[delay_index]
            time_since_last = current_time - self._last_connection_attempt

            if time_since_last < required_delay:
                remaining = required_delay - time_since_last
                self._logger.debug(
                    "Waiting %.1fs before reconnection attempt %d",
                    remaining,
                    self._connection_attempts + 1
                )
                await asyncio.sleep(remaining)

        self._connection_attempts += 1
        self._last_connection_attempt = time.time()

        self._logger.debug(
            "Connecting to Vevor Heater at %s (attempt %d)",
            self._ble_device.address,
            self._connection_attempts
        )

        try:
            # Establish connection with limited retries to avoid log spam
            # bleak_retry_connector will handle internal retries
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=3,  # Limit internal retries
            )

            # Verify services are available
            if not self._client.services:
                self._logger.warning("No services discovered, triggering service refresh")
                # Services might not be cached, disconnect and let next attempt retry
                await self._cleanup_connection()
                raise BleakError("No services available")

            # Get characteristic - try Vevor UUIDs first, then ABBA
            self._characteristic = None
            self._active_char_uuid = None
            self._is_abba_device = False
            self._abba_write_char = None

            # First, check for ABBA/HeaterCC device (service fff0)
            for service in self._client.services:
                if service.uuid.lower() == ABBA_SERVICE_UUID.lower():
                    self._logger.info("🔍 Detected ABBA/HeaterCC heater (service fff0)")
                    self._is_abba_device = True
                    self._protocol_mode = 5  # ABBA protocol
                    self._protocol = self._protocols[5]

                    # Log all characteristics in this service for debugging
                    char_list = [f"{c.uuid} (props: {c.properties})" for c in service.characteristics]
                    self._logger.info("📋 ABBA service characteristics: %s", char_list)

                    # Find notify and write characteristics
                    for char in service.characteristics:
                        if char.uuid.lower() == ABBA_NOTIFY_UUID.lower():
                            self._characteristic = char
                            self._active_char_uuid = ABBA_NOTIFY_UUID
                            self._logger.info("✅ Found ABBA notify characteristic (fff1): %s", char.uuid)
                        elif char.uuid.lower() == ABBA_WRITE_UUID.lower():
                            self._abba_write_char = char
                            self._logger.info("✅ Found ABBA write characteristic (fff2): %s", char.uuid)

                    # Warning if write characteristic not found
                    if not self._abba_write_char:
                        self._logger.warning(
                            "⚠️ ABBA device but fff2 write characteristic not found! "
                            "Will try writing to fff1 as fallback."
                        )
                        # Fall back to using fff1 for writing if fff2 not available
                        self._abba_write_char = self._characteristic
                    break

            # If not ABBA, try Vevor UUIDs
            if not self._is_abba_device:
                # Define UUID pairs to try: (service_uuid, characteristic_uuid)
                uuid_pairs = [
                    (SERVICE_UUID, CHARACTERISTIC_UUID),
                    (SERVICE_UUID_ALT, CHARACTERISTIC_UUID_ALT),
                ]

                for service_uuid, char_uuid in uuid_pairs:
                    for service in self._client.services:
                        if service.uuid.lower() == service_uuid.lower():
                            for char in service.characteristics:
                                if char.uuid.lower() == char_uuid.lower():
                                    self._characteristic = char
                                    self._active_char_uuid = char_uuid
                                    self._logger.info(
                                        "Found Vevor heater characteristic: %s (service: %s)",
                                        char_uuid, service_uuid
                                    )
                                    break
                            if self._characteristic:
                                break
                    if self._characteristic:
                        break

            if not self._characteristic:
                # Log available services for debugging
                available_services = [s.uuid for s in self._client.services]
                self._logger.error(
                    "Could not find heater characteristic. Available services: %s",
                    available_services
                )
                await self._cleanup_connection()
                raise BleakError("Could not find heater characteristic")

            # Start notifications on the discovered characteristic
            if "notify" in self._characteristic.properties:
                await self._client.start_notify(
                    self._active_char_uuid, self._notification_callback
                )
                self._logger.debug("Started notifications on %s", self._active_char_uuid)
            else:
                self._logger.warning("Characteristic does not support notify")

            # Send a wake-up ping to ensure device is responsive
            # Some heaters go into deep sleep and need a nudge
            self._logger.debug("Sending wake-up ping to device")
            await self._send_wake_up_ping()

            self._connection_attempts = 0  # Reset on successful connection
            self._logger.info("Successfully connected to Vevor Heater")

        except Exception as err:
            # Clean up on any connection failure
            await self._cleanup_connection()
            raise

    @callback
    def _notification_callback(self, _sender: int, data: bytearray) -> None:
        """Handle notification from heater."""
        # Log ALL received data for debugging
        self._logger.info(
            "📩 Received BLE data (%d bytes): %s",
            len(data),
            data.hex()
        )
        try:
            self._parse_response(data)
        except Exception as err:
            self._logger.error("Error parsing notification: %s", err)

    def _detect_protocol(
        self, data: bytearray, header: int
    ) -> tuple[HeaterProtocol | None, bytearray | None]:
        """Detect protocol from BLE data and return (protocol, data_to_parse).

        For encrypted protocols, data_to_parse is already decrypted.
        """
        if header == PROTOCOL_HEADER_CBFF:
            return self._protocols[6], data

        if header == PROTOCOL_HEADER_ABBA or self._is_abba_device:
            return self._protocols[5], data

        if len(data) < 17:
            return None, None

        if header == 0xAA55 and len(data) in (18, 20):
            return self._protocols[1], data

        if header == 0xAA66 and len(data) == 20:
            return self._protocols[3], data

        if len(data) == 48:
            decrypted = _decrypt_data(data)
            inner = (_u8_to_number(decrypted[0]) << 8) | _u8_to_number(decrypted[1])
            if inner == 0xAA55:
                return self._protocols[2], decrypted
            if inner == 0xAA66:
                return self._protocols[4], decrypted

        return None, None

    def _parse_response(self, data: bytearray) -> None:
        """Parse response from heater using protocol handler classes."""
        if len(data) < 8:
            # AA77 ACK is 10 bytes - check before discarding
            header_short = (_u8_to_number(data[0]) << 8) | _u8_to_number(data[1]) if len(data) >= 2 else 0
            if header_short == PROTOCOL_HEADER_AA77:
                self._logger.debug("AA77 ACK received (%d bytes)", len(data))
                self._notification_data = data
                return
            self._logger.debug("Response too short: %d bytes", len(data))
            return

        header = (_u8_to_number(data[0]) << 8) | _u8_to_number(data[1])

        # Check for AA77 command ACK (Sunster heaters respond to AA55 with AA77)
        if header == PROTOCOL_HEADER_AA77:
            self._logger.debug("AA77 ACK received (%d bytes)", len(data))
            self._notification_data = data
            return

        old_mode = self._protocol_mode

        # Detect protocol and get data to parse (may be decrypted)
        protocol, parse_data = self._detect_protocol(data, header)
        if not protocol:
            self._logger.warning(
                "Unknown protocol, length: %d, header: 0x%04X", len(data), header
            )
            return

        self._protocol_mode = protocol.protocol_mode
        self._protocol = protocol

        # Parse
        try:
            parsed = protocol.parse(parse_data)
        except Exception as err:
            self._logger.error("%s parse error: %s", protocol.name, err)
            self.data.update({
                "connected": True,
                "running_state": 0,
                "running_step": 0,
                "error_code": 0,
            })
            self._notification_data = data
            return

        if parsed is None:
            self.data["connected"] = True
            self._notification_data = data
            return

        # CBFF decryption status logging
        if parsed.pop("_cbff_decrypted", False):
            self._logger.info(
                "CBFF data decrypted successfully (device_sn=%s)",
                self.address.replace(":", "").upper(),
            )
        elif parsed.pop("_cbff_data_suspect", False):
            proto_ver = parsed.pop("cbff_protocol_version", "?")
            self._logger.warning(
                "CBFF data appears encrypted or corrupt (protocol_version=%s, "
                "raw=%s). Sensor values discarded — only connection state kept. "
                "Please report this on GitHub Issue #24 with your heater model.",
                proto_ver, data.hex(),
            )

        self.data.update(parsed)

        # Update coordinator state from parsed data
        if "temp_unit" in parsed:
            self._heater_uses_fahrenheit = (parsed["temp_unit"] == 1)

        # Apply temperature calibration (ABBA handles it internally)
        if protocol.needs_calibration:
            self._apply_ui_temperature_offset()

        self._logger.debug("Parsed %s: %s", protocol.name, parsed)
        self._notification_data = data

        # Log protocol change
        if old_mode != self._protocol_mode:
            self._logger.info(
                "Protocol mode changed: %d -> %d (%s)",
                old_mode, self._protocol_mode, protocol.name
            )

    def _apply_ui_temperature_offset(self) -> None:
        """Apply HA-side UI temperature offset (display only, not sent to heater).

        Two purposes:
        1. Calculate cab_temperature_raw — the true sensor value before the
           heater's BLE offset. Needed by _async_calculate_auto_offset().
        2. Apply the manual HA-side display offset (CONF_TEMPERATURE_OFFSET)
           from the integration config. This only affects what HA displays,
           it does NOT send anything to the heater.

        Note: The heater's own BLE offset (cmd 20) is handled by the heater
        itself; we only read it from byte 34 of the response.

        Not called for ABBA protocol (sets cab_temperature_raw directly).
        """
        # Get reported temperature (already set by protocol parser)
        # This is AFTER the heater's internal offset has been applied
        reported_temp = self.data.get("cab_temperature")
        if reported_temp is None:
            return

        # Calculate the TRUE raw sensor temperature (before heater's internal offset)
        # Formula: raw_sensor_temp = reported_temp - heater_offset
        # Example: reported=18°C, heater_offset=-2°C → raw_sensor=18-(-2)=20°C
        heater_offset = self.data.get("heater_offset", 0)
        raw_sensor_temp = reported_temp - heater_offset
        self.data["cab_temperature_raw"] = raw_sensor_temp

        # Get configured manual offset (default to 0.0 if not set)
        # This is an HA-side display offset, separate from the heater offset
        manual_offset = self.config_entry.data.get(CONF_TEMPERATURE_OFFSET, DEFAULT_TEMPERATURE_OFFSET)

        # Apply manual offset for display purposes
        if manual_offset != 0.0:
            calibrated_temp = reported_temp + manual_offset

            # Clamp to sensor range
            calibrated_temp = max(SENSOR_TEMP_MIN, min(SENSOR_TEMP_MAX, calibrated_temp))

            # Round to 1 decimal place
            calibrated_temp = round(calibrated_temp, 1)

            # Update data with calibrated value
            self.data["cab_temperature"] = calibrated_temp

            self._logger.debug(
                "Applied HA display offset: reported=%s°C, ha_offset=%s°C, display=%s°C, raw_sensor=%s°C (heater_offset=%s°C)",
                reported_temp, manual_offset, calibrated_temp, raw_sensor_temp, heater_offset
            )

        # Note: heater_offset is now read from byte 34 of the response,
        # so we don't overwrite it here. It shows what the heater reports.

    async def _cleanup_connection(self) -> None:
        """Clean up BLE connection properly."""
        if self._client:
            try:
                if self._client.is_connected:
                    # Stop notifications using the active UUID
                    if self._characteristic and self._active_char_uuid and "notify" in self._characteristic.properties:
                        try:
                            await self._client.stop_notify(self._active_char_uuid)
                            self._logger.debug("Stopped notifications on %s", self._active_char_uuid)
                        except Exception as err:
                            self._logger.debug("Could not stop notifications: %s", err)

                    # Disconnect
                    await self._client.disconnect()
                    self._logger.debug("Disconnected from heater")
            except Exception as err:
                self._logger.debug("Error during cleanup: %s", err)
            finally:
                self._client = None
                self._characteristic = None
                self._active_char_uuid = None

    async def _write_gatt(self, packet: bytearray) -> None:
        """Write a packet to the appropriate BLE characteristic.

        Uses response=False to avoid authorization issues with BLE
        proxies (e.g., ESPHome BLE proxy). The heater sends a notification as response.
        """
        if self._is_abba_device and self._abba_write_char:
            write_char = self._abba_write_char
            protocol_name = "ABBA"
        else:
            write_char = self._characteristic
            protocol_name = "AAXX"

        await self._client.write_gatt_char(write_char, packet, response=False)
        self._logger.debug("Packet %s written to %s BLE characteristic", packet.hex(), protocol_name)

    async def _send_wake_up_ping(self) -> None:
        """Send a wake-up ping to the device to ensure it's responsive."""
        try:
            if self._client and (self._characteristic or self._abba_write_char):
                packet = self._build_command_packet(1)
                await self._write_gatt(packet)
                await asyncio.sleep(0.5)
                self._logger.debug("Wake-up ping sent")
        except Exception as err:
            self._logger.debug("Wake-up ping failed (non-critical): %s", err)

    def _build_command_packet(self, command: int, argument: int = 0) -> bytearray:
        """Build command packet for the heater.

        Delegates to the active protocol's command builder.
        Falls back to ABBA if _is_abba_device, else AA55.
        """
        if self._protocol:
            protocol = self._protocol
        elif self._is_abba_device:
            protocol = self._protocols[5]
        else:
            protocol = self._protocols[1]
        packet = protocol.build_command(command, argument, self._passkey)
        self._logger.debug(
            "Command packet (%d bytes, %s): %s", len(packet), protocol.name, packet.hex()
        )
        return packet

    async def _send_command(self, command: int, argument: int, timeout: float = 5.0) -> bool:
        """Send command to heater with configurable timeout.

        Args:
            command: Command code (1=status, 2=mode, 3=on/off, 4=level/temp, etc.)
            argument: Command argument
            timeout: Timeout in seconds for waiting response
        """
        if not self._client or not self._client.is_connected:
            self._logger.info(
                "Cannot send command: heater not connected. "
                "The integration will attempt to reconnect automatically."
            )
            return False

        if not self._characteristic:
            self._logger.error(
                "Cannot send command: BLE characteristic not found. "
                "Try reloading the integration."
            )
            return False

        # Build protocol-aware command packet
        packet = self._build_command_packet(command, argument)

        self._logger.info(
            "📤 Sending command: %s (cmd=%d, arg=%d, protocol=%d, len=%d)",
            packet.hex(), command, argument, self._protocol_mode, len(packet)
        )

        try:
            self._notification_data = None

            await self._write_gatt(packet)

            # For protocols that need it (e.g. ABBA), send a follow-up status request
            if self._protocol and self._protocol.needs_post_status and command != 1:
                await asyncio.sleep(0.5)
                status_packet = self._protocol.build_command(1, 0, self._passkey)
                await self._write_gatt(status_packet)
                self._logger.debug("%s: Sent follow-up status request", self._protocol.name)

            # Wait for notification with configurable timeout
            # Increased from 2s to 5s default to handle slow BLE responses
            iterations = int(timeout / 0.1)
            for i in range(iterations):
                await asyncio.sleep(0.1)
                if self._notification_data:
                    self._logger.info(
                        "✅ Received response after %.1fs (protocol=%d)",
                        i * 0.1, self._protocol_mode
                    )
                    return True

            self._logger.info("No response received after %.1fs", timeout)
            return False

        except Exception as err:
            self._logger.error("❌ Error sending command: %s", err)
            # On write error, the connection might be dead
            await self._cleanup_connection()
            return False

    async def async_turn_on(self) -> None:
        """Turn heater on."""
        # ABBA uses a toggle command (0xA1) for both ON and OFF.
        # Guard against accidental toggle: skip if already heating.
        if self._protocol_mode == 5 and self.data.get("running_state", 0) == 1:
            self._logger.info("ABBA: Heater already on, skipping toggle command")
            return
        success = await self._send_command(3, 1)
        if success:
            await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn heater off."""
        # ABBA uses a toggle command (0xA1) for both ON and OFF.
        # Guard against accidental toggle: skip if already off.
        if self._protocol_mode == 5 and self.data.get("running_state", 0) == 0:
            self._logger.info("ABBA: Heater already off, skipping toggle command")
            return
        success = await self._send_command(3, 0)
        if success:
            await self.async_request_refresh()

    async def async_set_level(self, level: int) -> None:
        """Set heater level (1-10)."""
        # Command 4 for level (verified with BYD heater)
        level = max(1, min(10, level))
        success = await self._send_command(4, level)
        if success:
            await self.async_request_refresh()

    async def async_set_temperature(self, temperature: int) -> None:
        """Set target temperature (8-36°C).

        Note: Temperature mode only accepts values 8-36°C.
        Values below 8 will be clamped to 8.

        The temperature unit (Celsius or Fahrenheit) is auto-detected from the
        heater's response. We send commands in the same unit the heater uses.
        """
        # Clamp to valid Celsius range
        temperature = max(8, min(36, temperature))
        current_temp = self.data.get("set_temp", "unknown")
        current_mode = self.data.get("running_mode", "unknown")

        # Send temperature in the unit the heater expects (detected from response)
        # Some mode 4 heaters use Fahrenheit, others use Celsius
        if self._heater_uses_fahrenheit:
            temp_fahrenheit = round(temperature * 9 / 5 + 32)
            self._logger.info(
                "🌡️ SET TEMPERATURE REQUEST: target=%d°C (%d°F), current=%s, mode=%s, protocol=%d (heater uses Fahrenheit)",
                temperature, temp_fahrenheit, current_temp, current_mode, self._protocol_mode
            )
            command_temp = temp_fahrenheit
        else:
            self._logger.info(
                "🌡️ SET TEMPERATURE REQUEST: target=%d°C, current=%s, mode=%s, protocol=%d (heater uses Celsius)",
                temperature, current_temp, current_mode, self._protocol_mode
            )
            command_temp = temperature

        success = await self._send_command(4, command_temp)

        if success:
            await self.async_request_refresh()
            # Log result after refresh
            new_temp = self.data.get("set_temp", "unknown")
            self._logger.info(
                "🌡️ SET TEMPERATURE RESULT: requested=%d°C, heater_reports=%s°C, %s",
                temperature, new_temp,
                "✅ SUCCESS" if new_temp == temperature else "❌ FAILED - heater did not accept"
            )
        else:
            self._logger.warning("🌡️ SET TEMPERATURE FAILED: command not sent successfully")

    async def async_set_mode(self, mode: int) -> None:
        """Set running mode (0=Manual, 1=Level, 2=Temperature, 3=Ventilation).

        Mode 3 (Ventilation) is ABBA-only and only works when heater is in standby.
        It activates fan-only mode without heating.
        """
        # Ventilation mode (ABBA only)
        if mode == 3:
            if self._protocol_mode != 5:
                self._logger.warning("Ventilation mode is only available for ABBA devices")
                return

            running_step = self.data.get("running_step", 0)
            if running_step not in (0, 6):  # STANDBY or VENTILATION
                self._logger.warning(
                    "Ventilation mode only available when heater is off (current step: %d)",
                    running_step
                )
                return

            self._logger.info("Activating ventilation mode (ABBA 0xA4)")
            success = await self._send_command(101, 0)  # Command 101 = ventilation
            if success:
                await self.async_request_refresh()
            return

        # Standard modes (0-2)
        mode = max(0, min(2, mode))
        self._logger.info("Setting running mode to %d", mode)
        success = await self._send_command(2, mode)
        if success:
            await self.async_request_refresh()

    async def async_set_auto_start_stop(self, enabled: bool) -> None:
        """Set Automatic Start/Stop mode (cmd 18).

        When enabled in Temperature mode, the heater will completely stop
        when the room temperature reaches 2°C above the target, and restart
        when it drops 2°C below the target.
        """
        self._logger.info("Setting Auto Start/Stop to %s", "enabled" if enabled else "disabled")
        # Command 18, arg=1 for enabled, arg=0 for disabled
        success = await self._send_command(18, 1 if enabled else 0)
        if success:
            await self.async_request_refresh()

    async def async_sync_time(self) -> None:
        """Sync heater time with Home Assistant time (cmd 10).

        The time is sent as: 60 * hours + minutes
        Example: 14:30 = 60 * 14 + 30 = 870
        """
        now = datetime.now()
        time_value = 60 * now.hour + now.minute
        self._logger.info("Syncing heater time to %02d:%02d (value=%d)", now.hour, now.minute, time_value)
        # Command 10 for time sync
        success = await self._send_command(10, time_value)
        if success:
            self._logger.info("✅ Time sync successful")
        else:
            self._logger.warning("❌ Time sync failed")

    async def async_set_heater_offset(self, offset: int) -> None:
        """Set temperature offset on the heater (cmd 20).

        This sends the offset value directly to the heater's control board.
        The heater will then use this offset for its own temperature readings
        and auto-start/stop logic.

        Both positive and negative offsets are supported via BLE.
        Encoding discovered by @Xev:
        - arg1 (packet[5]) = offset % 256 (value in two's complement)
        - arg2 (packet[6]) = (offset // 256) % 256 (0x00 for positive, 0xff for negative)

        Args:
            offset: Temperature offset in °C (-10 to +10, clamped)
        """
        # Clamp to valid range
        offset = max(MIN_HEATER_OFFSET, min(MAX_HEATER_OFFSET, offset))

        self._logger.info("🌡️ Setting heater temperature offset to %d°C (cmd 20)", offset)

        # Command 20 for temperature offset
        # Pass offset directly - _build_command_packet handles encoding
        success = await self._send_command(20, offset)

        if success:
            self._current_heater_offset = offset
            self.data["heater_offset"] = offset
            self._logger.info("✅ Heater offset set to %d°C", offset)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set heater offset")

    async def async_set_language(self, language: int) -> None:
        """Set voice notification language (cmd 14).

        Args:
            language: Language code (0=Chinese, 1=English, 2=Russian, etc.)
        """
        self._logger.info("🗣️ Setting language to %d (cmd 14)", language)
        success = await self._send_command(14, language)
        if success:
            self.data["language"] = language
            self._logger.info("✅ Language set to %d", language)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set language")

    async def async_set_temp_unit(self, use_fahrenheit: bool) -> None:
        """Set temperature unit (cmd 15).

        Args:
            use_fahrenheit: True for Fahrenheit, False for Celsius
        """
        value = 1 if use_fahrenheit else 0
        unit_name = "Fahrenheit" if use_fahrenheit else "Celsius"
        self._logger.info("🌡️ Setting temperature unit to %s (cmd 15, value=%d)", unit_name, value)
        success = await self._send_command(15, value)
        if success:
            self.data["temp_unit"] = value
            self._heater_uses_fahrenheit = use_fahrenheit
            self._logger.info("✅ Temperature unit set to %s", unit_name)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set temperature unit")

    async def async_set_altitude_unit(self, use_feet: bool) -> None:
        """Set altitude unit (cmd 19).

        Args:
            use_feet: True for Feet, False for Meters
        """
        value = 1 if use_feet else 0
        unit_name = "Feet" if use_feet else "Meters"
        self._logger.info("📏 Setting altitude unit to %s (cmd 19, value=%d)", unit_name, value)
        success = await self._send_command(19, value)
        if success:
            self.data["altitude_unit"] = value
            self._logger.info("✅ Altitude unit set to %s", unit_name)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set altitude unit")

    async def async_set_high_altitude(self, enabled: bool) -> None:
        """Toggle high altitude mode (ABBA-only, cmd 99).

        The ABBA protocol uses a toggle command for high altitude mode.
        """
        if not self._is_abba_device:
            self._logger.warning("High altitude mode is only available for ABBA/HeaterCC devices")
            return
        state_name = "ON" if enabled else "OFF"
        self._logger.info("🏔️ Setting high altitude mode to %s", state_name)
        success = await self._send_command(99, 0)
        if success:
            self.data["high_altitude"] = 1 if enabled else 0
            self._logger.info("✅ High altitude mode set to %s", state_name)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set high altitude mode")

    async def async_set_tank_volume(self, volume_index: int) -> None:
        """Set tank volume by index (cmd 16).

        The heater uses index-based values, not actual liters:
        0=None, 1=5L, 2=10L, 3=15L, 4=20L, 5=25L, 6=30L, 7=35L, 8=40L, 9=45L, 10=50L

        Args:
            volume_index: Tank volume index (0-10)
        """
        volume_index = max(0, min(10, volume_index))
        self._logger.info("⛽ Setting tank volume to index %d (cmd 16)", volume_index)
        success = await self._send_command(16, volume_index)
        if success:
            self.data["tank_volume"] = volume_index
            self._logger.info("✅ Tank volume set to index %d", volume_index)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set tank volume")

    async def async_set_pump_type(self, pump_type: int) -> None:
        """Set oil pump type (cmd 17).

        Pump types: 0=16µl, 1=22µl, 2=28µl, 3=32µl

        Args:
            pump_type: Pump type (0-3)
        """
        pump_type = max(0, min(3, pump_type))
        self._logger.info("🔧 Setting pump type to %d (cmd 17)", pump_type)
        success = await self._send_command(17, pump_type)
        if success:
            self.data["pump_type"] = pump_type
            self._logger.info("✅ Pump type set to %d", pump_type)
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ Failed to set pump type")

    async def async_set_backlight(self, level: int) -> None:
        """Set display backlight brightness (cmd 21).

        Values: 0=Off, 1-10, 20-100 (in steps of 10).
        The heater may round to nearest supported value.

        Args:
            level: Brightness level (0-100)
        """
        level = max(0, min(100, level))
        self._logger.info("Setting backlight to %d (cmd 21)", level)
        success = await self._send_command(21, level)
        if success:
            self.data["backlight"] = level
            self._logger.info("Backlight set to %d", level)
            await self.async_request_refresh()
        else:
            self._logger.warning("Failed to set backlight")

    async def async_set_auto_offset_enabled(self, enabled: bool) -> None:
        """Enable or disable automatic temperature offset adjustment.

        When enabled, the integration will automatically calculate and send
        temperature offset commands to the heater based on an external
        temperature sensor.

        Args:
            enabled: True to enable, False to disable
        """
        self._logger.info("Setting auto offset to %s", "enabled" if enabled else "disabled")
        self.data["auto_offset_enabled"] = enabled

        # Persist the setting immediately
        await self.async_save_data()

        if enabled:
            # Trigger initial calculation
            await self._async_calculate_auto_offset()
        else:
            # Reset heater offset to 0 when disabling
            if self._current_heater_offset != 0:
                self._logger.info("Resetting heater offset to 0")
                await self.async_set_heater_offset(0)

    async def async_send_raw_command(self, command: int, argument: int) -> bool:
        """Send a raw command to the heater for debugging purposes.

        This allows testing different command numbers to discover the correct
        command for various heater functions.

        Args:
            command: Command number (0-255)
            argument: Argument value (-128 to 127, encoded as two's complement)

        Returns:
            True if command was sent successfully
        """
        self._logger.info(
            "🔧 DEBUG: Sending raw command: cmd=%d, arg=%d",
            command, argument
        )

        success = await self._send_command(command, argument)

        if success:
            self._logger.info("✅ DEBUG: Raw command sent successfully")
            await self.async_request_refresh()
        else:
            self._logger.warning("❌ DEBUG: Failed to send raw command")

        return success

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        self._logger.debug("Shutting down Vevor Heater coordinator")

        # Clean up external sensor listener
        if self._auto_offset_unsub:
            self._auto_offset_unsub()
            self._auto_offset_unsub = None

        await self._cleanup_connection()
