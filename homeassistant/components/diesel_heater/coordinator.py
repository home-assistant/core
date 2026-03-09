"""Coordinator for Diesel Heater."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ABBA_NOTIFY_UUID,
    ABBA_SERVICE_UUID,
    ABBA_WRITE_UUID,
    CHARACTERISTIC_UUID,
    CHARACTERISTIC_UUID_ALT,
    CONF_PIN,
    CONF_TEMPERATURE_OFFSET,
    DEFAULT_PIN,
    DEFAULT_TEMPERATURE_OFFSET,
    DOMAIN,
    MAX_HEATER_OFFSET,
    MIN_HEATER_OFFSET,
    PROTOCOL_HEADER_AA77,
    PROTOCOL_HEADER_ABBA,
    PROTOCOL_HEADER_CBFF,
    SENSOR_TEMP_MAX,
    SENSOR_TEMP_MIN,
    SERVICE_UUID,
    SERVICE_UUID_ALT,
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
        """Add heater ID prefix to log messages."""
        return f"[{self.extra['heater_id']}] {msg}", kwargs


class VevorHeaterCoordinator(DataUpdateCoordinator):
    """Diesel Heater coordinator."""

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
            config_entry=config_entry,
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
            "cab_temperature_raw": None,
            "heater_offset": 0,
            "connected": False,
            "auto_start_stop": None,
            "language": None,
            "temp_unit": None,
            "tank_volume": None,
            "pump_type": None,
            "altitude_unit": None,
            "rf433_enabled": None,
        }

    @property
    def protocol_mode(self) -> int:
        """Return the detected BLE protocol mode (0=unknown, 1-6=detected)."""
        return self._protocol_mode

    # Fields that represent volatile heater state (cleared on disconnect)
    _VOLATILE_FIELDS = (
        "case_temperature", "cab_temperature", "cab_temperature_raw",
        "supply_voltage", "running_state", "running_step", "running_mode",
        "set_level", "set_temp", "altitude", "error_code",
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
                    "Diesel Heater offline after %d attempts: %s",
                    self._consecutive_failures,
                    err
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from the heater."""
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
        current_time = time.monotonic()
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
        self._last_connection_attempt = time.monotonic()

        self._logger.debug(
            "Connecting to Diesel Heater at %s (attempt %d)",
            self._ble_device.address,
            self._connection_attempts
        )

        try:
            # Establish connection with limited retries to avoid log spam
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=3,
            )

            # Verify services are available
            if not self._client.services:
                self._logger.warning("No services discovered, triggering service refresh")
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
                    self._logger.debug("Detected ABBA/HeaterCC heater (service fff0)")
                    self._is_abba_device = True
                    self._protocol_mode = 5  # ABBA protocol
                    self._protocol = self._protocols[5]

                    # Find notify and write characteristics
                    for char in service.characteristics:
                        if char.uuid.lower() == ABBA_NOTIFY_UUID.lower():
                            self._characteristic = char
                            self._active_char_uuid = ABBA_NOTIFY_UUID
                        elif char.uuid.lower() == ABBA_WRITE_UUID.lower():
                            self._abba_write_char = char

                    if not self._abba_write_char:
                        self._logger.warning(
                            "ABBA device but fff2 write characteristic not found! "
                            "Will try writing to fff1 as fallback."
                        )
                        self._abba_write_char = self._characteristic
                    break

            # If not ABBA, try Vevor UUIDs
            if not self._is_abba_device:
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
                                        "Found heater characteristic: %s (service: %s)",
                                        char_uuid, service_uuid
                                    )
                                    break
                            if self._characteristic:
                                break
                    if self._characteristic:
                        break

            if not self._characteristic:
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
            self._logger.debug("Sending wake-up ping to device")
            await self._send_wake_up_ping()

            self._connection_attempts = 0  # Reset on successful connection
            self._logger.info("Successfully connected to Diesel Heater")

        except Exception:
            await self._cleanup_connection()
            raise

    @callback
    def _notification_callback(self, _sender: int, data: bytearray) -> None:
        """Handle notification from heater."""
        self._logger.debug(
            "Received BLE data (%d bytes): %s",
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
            header_short = (_u8_to_number(data[0]) << 8) | _u8_to_number(data[1]) if len(data) >= 2 else 0
            if header_short == PROTOCOL_HEADER_AA77:
                self._logger.debug("AA77 ACK received (%d bytes)", len(data))
                self._notification_data = data
                return
            self._logger.debug("Response too short: %d bytes", len(data))
            return

        header = (_u8_to_number(data[0]) << 8) | _u8_to_number(data[1])

        # Check for AA77 command ACK
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

        # Parse using HeaterState for structured access
        try:
            state = protocol.parse_to_state(parse_data)
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

        if state is None:
            self.data["connected"] = True
            self._notification_data = data
            return

        # Convert HeaterState to dict for self.data
        parsed = state.as_dict()

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

        Calculates cab_temperature_raw (true sensor value before heater offset)
        and applies the manual HA-side display offset from config.
        Not called for ABBA protocol (sets cab_temperature_raw directly).
        """
        reported_temp = self.data.get("cab_temperature")
        if reported_temp is None:
            return

        # Calculate TRUE raw sensor temperature (before heater's internal offset)
        heater_offset = self.data.get("heater_offset", 0)
        raw_sensor_temp = reported_temp - heater_offset
        self.data["cab_temperature_raw"] = raw_sensor_temp

        # Get configured manual offset
        manual_offset = self.config_entry.data.get(CONF_TEMPERATURE_OFFSET, DEFAULT_TEMPERATURE_OFFSET)

        # Apply manual offset for display purposes
        if manual_offset != 0.0:
            calibrated_temp = reported_temp + manual_offset
            calibrated_temp = max(SENSOR_TEMP_MIN, min(SENSOR_TEMP_MAX, calibrated_temp))
            calibrated_temp = round(calibrated_temp, 1)
            self.data["cab_temperature"] = calibrated_temp

    async def _cleanup_connection(self) -> None:
        """Clean up BLE connection properly."""
        if self._client:
            try:
                if self._client.is_connected:
                    if self._characteristic and self._active_char_uuid and "notify" in self._characteristic.properties:
                        try:
                            await self._client.stop_notify(self._active_char_uuid)
                        except Exception as err:
                            self._logger.debug("Could not stop notifications: %s", err)
                    await self._client.disconnect()
            except Exception as err:
                self._logger.debug("Error during cleanup: %s", err)
            finally:
                self._client = None
                self._characteristic = None
                self._active_char_uuid = None

    async def _write_gatt(self, packet: bytearray) -> None:
        """Write a packet to the appropriate BLE characteristic."""
        if self._is_abba_device and self._abba_write_char:
            write_char = self._abba_write_char
        else:
            write_char = self._characteristic

        await self._client.write_gatt_char(write_char, packet, response=False)

    async def _send_wake_up_ping(self) -> None:
        """Send a wake-up ping to the device to ensure it's responsive."""
        try:
            if self._client and (self._characteristic or self._abba_write_char):
                packet = self._build_command_packet(1)
                await self._write_gatt(packet)
                await asyncio.sleep(0.5)
        except Exception as err:
            self._logger.debug("Wake-up ping failed (non-critical): %s", err)

    def _build_command_packet(self, command: int, argument: int = 0) -> bytearray:
        """Build command packet for the heater."""
        if self._protocol:
            protocol = self._protocol
        elif self._is_abba_device:
            protocol = self._protocols[5]
        else:
            protocol = self._protocols[1]
        return protocol.build_command(command, argument, self._passkey)

    async def _send_command(self, command: int, argument: int, timeout: float = 5.0) -> bool:
        """Send command to heater with configurable timeout."""
        if not self._client or not self._client.is_connected:
            self._logger.warning("Cannot send command: heater not connected")
            return False

        if not self._characteristic:
            self._logger.error("Cannot send command: BLE characteristic not found")
            return False

        packet = self._build_command_packet(command, argument)

        self._logger.debug(
            "Sending command: %s (cmd=%d, arg=%d, protocol=%d)",
            packet.hex(), command, argument, self._protocol_mode
        )

        try:
            self._notification_data = None

            await self._write_gatt(packet)

            # For protocols that need it, send a follow-up status request
            if self._protocol and self._protocol.needs_post_status and command != 1:
                await asyncio.sleep(0.5)
                status_packet = self._protocol.build_command(1, 0, self._passkey)
                await self._write_gatt(status_packet)

            # Wait for notification
            iterations = int(timeout / 0.1)
            for i in range(iterations):
                await asyncio.sleep(0.1)
                if self._notification_data:
                    self._logger.debug(
                        "Received response after %.1fs (protocol=%d)",
                        i * 0.1, self._protocol_mode
                    )
                    return True

            self._logger.debug("No response received after %.1fs", timeout)
            return False

        except Exception as err:
            self._logger.error("Error sending command: %s", err)
            await self._cleanup_connection()
            return False

    async def async_turn_on(self) -> None:
        """Turn heater on."""
        # ABBA uses a toggle command for both ON and OFF
        if self._protocol_mode == 5 and self.data.get("running_state", 0) == 1:
            self._logger.debug("ABBA: Heater already on, skipping toggle command")
            return
        success = await self._send_command(3, 1)
        if success:
            await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn heater off."""
        if self._protocol_mode == 5 and self.data.get("running_state", 0) == 0:
            self._logger.debug("ABBA: Heater already off, skipping toggle command")
            return
        success = await self._send_command(3, 0)
        if success:
            await self.async_request_refresh()

    async def async_set_level(self, level: int) -> None:
        """Set heater level (1-10)."""
        level = max(1, min(10, level))
        success = await self._send_command(4, level)
        if success:
            await self.async_request_refresh()

    async def async_set_temperature(self, temperature: int) -> None:
        """Set target temperature (8-36 C)."""
        temperature = max(8, min(36, temperature))

        # Send in the unit the heater expects
        if self._heater_uses_fahrenheit:
            command_temp = round(temperature * 9 / 5 + 32)
        else:
            command_temp = temperature

        success = await self._send_command(4, command_temp)
        if success:
            await self.async_request_refresh()

    async def async_set_mode(self, mode: int) -> None:
        """Set running mode (0=Manual, 1=Level, 2=Temperature, 3=Ventilation)."""
        # Ventilation mode (ABBA only)
        if mode == 3:
            if self._protocol_mode != 5:
                self._logger.warning("Ventilation mode is only available for ABBA devices")
                return
            running_step = self.data.get("running_step", 0)
            if running_step not in (0, 6):
                self._logger.warning(
                    "Ventilation mode only available when heater is off (current step: %d)",
                    running_step
                )
                return
            success = await self._send_command(101, 0)
            if success:
                await self.async_request_refresh()
            return

        mode = max(0, min(2, mode))
        success = await self._send_command(2, mode)
        if success:
            await self.async_request_refresh()

    async def async_set_auto_start_stop(self, enabled: bool) -> None:
        """Set Automatic Start/Stop mode (cmd 18)."""
        success = await self._send_command(18, 1 if enabled else 0)
        if success:
            await self.async_request_refresh()

    async def async_sync_time(self) -> None:
        """Sync heater time with Home Assistant time (cmd 10)."""
        now = dt_util.now()
        time_value = 60 * now.hour + now.minute
        await self._send_command(10, time_value)

    async def async_set_heater_offset(self, offset: int) -> None:
        """Set temperature offset on the heater (cmd 20)."""
        offset = max(MIN_HEATER_OFFSET, min(MAX_HEATER_OFFSET, offset))
        success = await self._send_command(20, offset)
        if success:
            self.data["heater_offset"] = offset
            await self.async_request_refresh()

    async def async_set_language(self, language: int) -> None:
        """Set voice notification language (cmd 14)."""
        success = await self._send_command(14, language)
        if success:
            self.data["language"] = language
            await self.async_request_refresh()

    async def async_set_temp_unit(self, use_fahrenheit: bool) -> None:
        """Set temperature unit (cmd 15)."""
        value = 1 if use_fahrenheit else 0
        success = await self._send_command(15, value)
        if success:
            self.data["temp_unit"] = value
            self._heater_uses_fahrenheit = use_fahrenheit
            await self.async_request_refresh()

    async def async_set_altitude_unit(self, use_feet: bool) -> None:
        """Set altitude unit (cmd 19)."""
        value = 1 if use_feet else 0
        success = await self._send_command(19, value)
        if success:
            self.data["altitude_unit"] = value
            await self.async_request_refresh()

    async def async_set_high_altitude(self, enabled: bool) -> None:
        """Toggle high altitude mode (ABBA-only, cmd 99)."""
        if not self._is_abba_device:
            self._logger.warning("High altitude mode is only available for ABBA/HeaterCC devices")
            return
        success = await self._send_command(99, 0)
        if success:
            self.data["high_altitude"] = 1 if enabled else 0
            await self.async_request_refresh()

    async def async_set_tank_volume(self, volume_index: int) -> None:
        """Set tank volume by index (cmd 16)."""
        volume_index = max(0, min(10, volume_index))
        success = await self._send_command(16, volume_index)
        if success:
            self.data["tank_volume"] = volume_index
            await self.async_request_refresh()

    async def async_set_pump_type(self, pump_type: int) -> None:
        """Set oil pump type (cmd 17)."""
        pump_type = max(0, min(3, pump_type))
        success = await self._send_command(17, pump_type)
        if success:
            self.data["pump_type"] = pump_type
            await self.async_request_refresh()

    async def async_set_backlight(self, level: int) -> None:
        """Set display backlight brightness (cmd 21)."""
        level = max(0, min(100, level))
        success = await self._send_command(21, level)
        if success:
            self.data["backlight"] = level
            await self.async_request_refresh()

    async def async_send_raw_command(self, command: int, argument: int) -> bool:
        """Send a raw command to the heater for debugging purposes."""
        self._logger.debug("Sending raw command: cmd=%d, arg=%d", command, argument)
        success = await self._send_command(command, argument)
        if success:
            await self.async_request_refresh()
        return success

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        self._logger.debug("Shutting down Diesel Heater coordinator")
        await self._cleanup_connection()
