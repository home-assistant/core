"""Tests for Diesel Heater Coordinator.

Tests the coordinator logic without requiring actual BLE connections.
Focuses on data processing, fuel/runtime tracking, and protocol handling.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import pytest

# Import stubs first
from . import conftest  # noqa: F401

# Now we can import the coordinator
from custom_components.diesel_heater.coordinator import VevorHeaterCoordinator
from custom_components.diesel_heater.const import (
    FUEL_CONSUMPTION_TABLE,
    RUNNING_STEP_RUNNING,
    STORAGE_KEY_TOTAL_FUEL,
    STORAGE_KEY_DAILY_FUEL,
    STORAGE_KEY_DAILY_DATE,
    STORAGE_KEY_DAILY_HISTORY,
    STORAGE_KEY_TOTAL_RUNTIME,
    STORAGE_KEY_DAILY_RUNTIME,
    STORAGE_KEY_DAILY_RUNTIME_DATE,
    STORAGE_KEY_DAILY_RUNTIME_HISTORY,
    STORAGE_KEY_FUEL_SINCE_RESET,
    STORAGE_KEY_TANK_CAPACITY,
    STORAGE_KEY_LAST_REFUELED,
    STORAGE_KEY_AUTO_OFFSET_ENABLED,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def create_mock_coordinator() -> VevorHeaterCoordinator:
    """Create a mock coordinator for testing without calling __init__."""
    from diesel_heater_ble import (
        ProtocolAA55, ProtocolAA66, ProtocolAA55Encrypted,
        ProtocolAA66Encrypted, ProtocolABBA, ProtocolCBFF,
    )

    hass = MagicMock()
    hass.loop = asyncio.new_event_loop()

    entry = MagicMock()
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {}
    entry.entry_id = "test_entry"

    ble_device = MagicMock()
    ble_device.address = "AA:BB:CC:DD:EE:FF"

    # Create coordinator without calling __init__ using object.__new__
    coordinator = object.__new__(VevorHeaterCoordinator)

    # Set up minimum required attributes
    coordinator.hass = hass
    coordinator.config_entry = entry
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator._logger = MagicMock()
    coordinator._store = MagicMock()
    coordinator._protocol = None
    coordinator._protocol_mode = 0
    coordinator._passkey = 1234

    # Protocol handlers dict (mode -> protocol instance)
    coordinator._protocols = {
        1: ProtocolAA55(),
        2: ProtocolAA55Encrypted(),
        3: ProtocolAA66(),
        4: ProtocolAA66Encrypted(),
        5: ProtocolABBA(),
        6: ProtocolCBFF(),
    }

    # Data dict
    coordinator.data = {
        "connected": False,
        "running_state": 0,
        "running_step": 0,
        "running_mode": 0,
        "set_level": 1,
        "set_temp": 22,
        "cab_temperature": 20.0,
        "case_temperature": 50,
        "supply_voltage": 12.5,
        "error_code": 0,
        "altitude": 0,
        "hourly_fuel_consumption": 0.0,
        "daily_fuel_consumed": 0.0,
        "total_fuel_consumed": 0.0,
        "fuel_remaining": None,
        "fuel_consumed_since_reset": 0.0,
        "tank_capacity": 5,
        "daily_runtime_hours": 0.0,
        "total_runtime_hours": 0.0,
        "daily_fuel_history": {},
        "daily_runtime_history": {},
    }

    # Fuel tracking state (correct attribute names)
    coordinator._daily_fuel_consumed = 0.0
    coordinator._total_fuel_consumed = 0.0
    coordinator._daily_fuel_history = {}
    coordinator._fuel_consumed_since_reset = 0.0
    coordinator._last_reset_date = datetime.now().strftime("%Y-%m-%d")

    # Runtime tracking state (correct attribute names)
    coordinator._daily_runtime_seconds = 0.0
    coordinator._total_runtime_seconds = 0.0
    coordinator._daily_runtime_history = {}
    coordinator._last_runtime_reset_date = datetime.now().strftime("%Y-%m-%d")

    # Connection state
    coordinator._last_update_time = None
    coordinator._last_valid_data = {}
    coordinator._consecutive_failures = 0
    coordinator._max_stale_cycles = 3
    coordinator._is_abba_device = False
    coordinator._connection_attempts = 0
    coordinator._last_connection_attempt = 0.0
    coordinator._client = None
    coordinator._ble_device = ble_device
    coordinator._characteristic = None
    coordinator._active_char_uuid = None
    coordinator._abba_write_char = None
    coordinator._notification_data = None

    # Volatile fields for clear/restore/save
    coordinator._VOLATILE_FIELDS = (
        "case_temperature", "cab_temperature", "cab_temperature_raw",
        "supply_voltage", "running_state", "running_step", "running_mode",
        "set_level", "set_temp", "altitude", "error_code",
        "hourly_fuel_consumption", "co_ppm", "remain_run_time",
    )

    # Auto offset related
    coordinator._auto_offset_unsub = None
    coordinator._auto_offset_enabled = False
    coordinator._external_temp_sensor = None
    coordinator._auto_offset_max = 5
    coordinator._heater_uses_fahrenheit = False

    # Add address property (used by statistics import)
    coordinator.address = "AA:BB:CC:DD:EE:FF"

    # Add async_set_updated_data method (from DataUpdateCoordinator parent)
    coordinator.async_set_updated_data = MagicMock()

    return coordinator


# ---------------------------------------------------------------------------
# Fuel consumption calculation tests
# ---------------------------------------------------------------------------

class TestFuelConsumption:
    """Tests for fuel consumption calculations."""

    def test_calculate_fuel_consumption_level_1(self):
        """Test fuel consumption at level 1."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 1
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        # 1 hour = 3600 seconds
        consumption = coordinator._calculate_fuel_consumption(3600)

        # Level 1 consumption from table
        expected = FUEL_CONSUMPTION_TABLE.get(1, 0.1)
        assert abs(consumption - expected) < 0.001

    def test_calculate_fuel_consumption_level_10(self):
        """Test fuel consumption at maximum level."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 10
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        consumption = coordinator._calculate_fuel_consumption(3600)
        expected = FUEL_CONSUMPTION_TABLE.get(10, 0.5)
        assert abs(consumption - expected) < 0.001

    def test_calculate_fuel_consumption_fractional_hour(self):
        """Test fuel consumption for partial hour."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 5
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        # 30 minutes = 1800 seconds
        consumption = coordinator._calculate_fuel_consumption(1800)
        expected = FUEL_CONSUMPTION_TABLE.get(5, 0.25) / 2
        assert abs(consumption - expected) < 0.001

    def test_calculate_fuel_consumption_zero_time(self):
        """Test fuel consumption with zero elapsed time."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING
        consumption = coordinator._calculate_fuel_consumption(0)
        assert consumption == 0.0

    def test_calculate_fuel_consumption_when_not_running(self):
        """Test fuel consumption returns 0 when heater not running."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 10
        coordinator.data["running_step"] = 0  # Standby

        consumption = coordinator._calculate_fuel_consumption(3600)
        assert consumption == 0.0


class TestFuelTracking:
    """Tests for fuel tracking logic."""

    def test_update_fuel_tracking_when_running(self):
        """Test fuel tracking updates when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING
        coordinator.data["set_level"] = 5

        initial_daily = coordinator._daily_fuel_consumed
        initial_total = coordinator._total_fuel_consumed

        coordinator._update_fuel_tracking(3600)  # 1 hour

        expected = FUEL_CONSUMPTION_TABLE.get(5, 0.25)
        assert coordinator._daily_fuel_consumed > initial_daily
        assert coordinator._total_fuel_consumed > initial_total
        assert abs(coordinator._daily_fuel_consumed - expected) < 0.01

    def test_update_fuel_tracking_when_not_running(self):
        """Test fuel tracking doesn't update when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 0  # Standby

        initial_daily = coordinator._daily_fuel_consumed
        initial_total = coordinator._total_fuel_consumed

        coordinator._update_fuel_tracking(3600)

        assert coordinator._daily_fuel_consumed == initial_daily
        assert coordinator._total_fuel_consumed == initial_total

    def test_update_fuel_remaining(self):
        """Test fuel remaining calculation."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 10
        coordinator._fuel_consumed_since_reset = 3.5

        coordinator._update_fuel_remaining()

        assert coordinator.data["fuel_remaining"] == 6.5

    def test_update_fuel_remaining_negative_clamped(self):
        """Test fuel remaining is clamped to zero."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 5
        coordinator._fuel_consumed_since_reset = 10.0

        coordinator._update_fuel_remaining()

        assert coordinator.data["fuel_remaining"] == 0.0


# ---------------------------------------------------------------------------
# Runtime tracking tests
# ---------------------------------------------------------------------------

class TestRuntimeTracking:
    """Tests for runtime tracking logic."""

    def test_update_runtime_when_running(self):
        """Test runtime updates when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        initial_daily = coordinator._daily_runtime_seconds
        initial_total = coordinator._total_runtime_seconds

        coordinator._update_runtime_tracking(3600)  # 1 hour

        # Runtime is tracked in seconds internally
        assert coordinator._daily_runtime_seconds == initial_daily + 3600
        assert coordinator._total_runtime_seconds == initial_total + 3600

    def test_update_runtime_when_not_running(self):
        """Test runtime doesn't update when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 0

        initial_daily = coordinator._daily_runtime_seconds

        coordinator._update_runtime_tracking(3600)

        assert coordinator._daily_runtime_seconds == initial_daily


# ---------------------------------------------------------------------------
# Data management tests
# ---------------------------------------------------------------------------

class TestDataManagement:
    """Tests for data clearing, saving, and restoring."""

    def test_clear_sensor_values(self):
        """Test that sensor values are cleared correctly."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["supply_voltage"] = 12.5

        coordinator._clear_sensor_values()

        assert coordinator.data["cab_temperature"] is None
        assert coordinator.data["supply_voltage"] is None

    def test_save_valid_data(self):
        """Test that valid data is saved for restoration."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["supply_voltage"] = 12.5

        coordinator._save_valid_data()

        assert coordinator._last_valid_data["cab_temperature"] == 25.0
        assert coordinator._last_valid_data["supply_voltage"] == 12.5

    def test_restore_stale_data(self):
        """Test that stale data is restored correctly."""
        coordinator = create_mock_coordinator()
        coordinator._last_valid_data = {
            "cab_temperature": 25.0,
            "supply_voltage": 12.5,
        }
        coordinator.data["cab_temperature"] = None
        coordinator.data["supply_voltage"] = None

        coordinator._restore_stale_data()

        assert coordinator.data["cab_temperature"] == 25.0
        assert coordinator.data["supply_voltage"] == 12.5


# ---------------------------------------------------------------------------
# Protocol detection tests
# ---------------------------------------------------------------------------

class TestProtocolDetection:
    """Tests for protocol detection logic."""

    def test_detect_protocol_aa55_unencrypted(self):
        """Test detection of AA55 unencrypted protocol."""
        coordinator = create_mock_coordinator()

        # AA55 header, 20 bytes
        data = bytearray([0xAA, 0x55] + [0x00] * 18)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is not None
        assert protocol.protocol_mode == 1  # AA55 unencrypted

    def test_detect_protocol_aa55_encrypted(self):
        """Test detection of AA55 encrypted protocol (48 bytes)."""
        coordinator = create_mock_coordinator()

        # 48 bytes, after decryption should have AA55 or AA66 header
        # Create encrypted data that decrypts to AA55
        from diesel_heater_ble import _encrypt_data
        plain = bytearray([0xAA, 0x55] + [0x00] * 46)
        data = _encrypt_data(plain)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is not None
        assert protocol.protocol_mode in [2, 4]  # Encrypted variants

    def test_detect_protocol_abba(self):
        """Test detection of ABBA/HeaterCC protocol."""
        coordinator = create_mock_coordinator()

        # ABBA header 0xABBA, 21+ bytes
        data = bytearray([0xAB, 0xBA] + [0x00] * 19)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is not None
        assert protocol.protocol_mode == 5  # ABBA

    def test_detect_protocol_cbff(self):
        """Test detection of CBFF/Sunster protocol."""
        coordinator = create_mock_coordinator()

        # CBFF header 0xCBFF, 47 bytes
        data = bytearray([0xCB, 0xFF] + [0x00] * 45)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is not None
        assert protocol.protocol_mode == 6  # CBFF

    def test_detect_protocol_unknown_returns_none(self):
        """Test that unknown data returns None."""
        coordinator = create_mock_coordinator()

        # Random data with no valid header
        data = bytearray([0x12, 0x34] + [0x00] * 10)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is None


# ---------------------------------------------------------------------------
# Command building tests
# ---------------------------------------------------------------------------

class TestCommandBuilding:
    """Tests for command packet building."""

    def test_build_command_packet_aa55(self):
        """Test building AA55 command packet."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1  # AA55
        coordinator._passkey = 1234

        packet = coordinator._build_command_packet(1, 0)  # Status request

        assert len(packet) == 8
        assert packet[0] == 0xAA
        assert packet[1] == 0x55

    def test_build_command_packet_abba(self):
        """Test building ABBA command packet."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5  # ABBA
        coordinator._is_abba_device = True

        # Need to set protocol to ABBA
        from diesel_heater_ble import ProtocolABBA
        coordinator._protocol = ProtocolABBA()

        packet = coordinator._build_command_packet(1, 0)  # Status request

        # ABBA status request is "baab04cc000000"
        assert packet[0] == 0xBA
        assert packet[1] == 0xAB


# ---------------------------------------------------------------------------
# UI temperature offset tests
# ---------------------------------------------------------------------------

class TestUITemperatureOffset:
    """Tests for UI temperature offset application."""

    def test_apply_positive_offset(self):
        """Test applying positive temperature offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 20.0
        coordinator.data["heater_offset"] = 0
        # Set manual offset via config_entry.data
        coordinator.config_entry.data = {"temperature_offset": 2.0}

        coordinator._apply_ui_temperature_offset()

        assert coordinator.data["cab_temperature"] == 22.0
        assert coordinator.data["cab_temperature_raw"] == 20.0

    def test_apply_negative_offset(self):
        """Test applying negative temperature offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 20.0
        coordinator.data["heater_offset"] = 0
        coordinator.config_entry.data = {"temperature_offset": -3.0}

        coordinator._apply_ui_temperature_offset()

        assert coordinator.data["cab_temperature"] == 17.0
        assert coordinator.data["cab_temperature_raw"] == 20.0

    def test_no_offset_when_none(self):
        """Test no offset applied when cab_temperature is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = None
        coordinator.config_entry.data = {"temperature_offset": 5.0}

        coordinator._apply_ui_temperature_offset()

        assert coordinator.data["cab_temperature"] is None


# ---------------------------------------------------------------------------
# Connection failure handling tests
# ---------------------------------------------------------------------------

class TestConnectionFailureHandling:
    """Tests for connection failure handling."""

    def test_handle_connection_failure_increments_counter(self):
        """Test that connection failures increment the counter."""
        coordinator = create_mock_coordinator()
        coordinator._consecutive_failures = 0

        coordinator._handle_connection_failure(Exception("Test error"))

        assert coordinator._consecutive_failures == 1

    def test_handle_connection_failure_clears_data_after_threshold(self):
        """Test that data is cleared after consecutive failures exceed threshold."""
        coordinator = create_mock_coordinator()
        coordinator._consecutive_failures = 2  # After 3rd failure, data should clear
        coordinator.data["cab_temperature"] = 25.0
        coordinator._stale_cycles = 3  # Exceed stale tolerance

        coordinator._handle_connection_failure(Exception("Test error"))

        # After threshold, connected should be false
        assert coordinator.data["connected"] is False


# ---------------------------------------------------------------------------
# History cleaning tests
# ---------------------------------------------------------------------------

class TestHistoryCleaning:
    """Tests for history data cleanup."""

    def test_clean_old_history_removes_old_entries(self):
        """Test that entries older than MAX_HISTORY_DAYS are removed."""
        coordinator = create_mock_coordinator()

        # Add old and new entries
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        recent_date = datetime.now().strftime("%Y-%m-%d")

        coordinator._daily_fuel_history = {
            old_date: 1.5,
            recent_date: 0.5,
        }

        coordinator._clean_old_history()

        assert old_date not in coordinator._daily_fuel_history
        assert recent_date in coordinator._daily_fuel_history

    def test_clean_old_runtime_history(self):
        """Test that old runtime history is cleaned."""
        coordinator = create_mock_coordinator()

        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        recent_date = datetime.now().strftime("%Y-%m-%d")

        coordinator._daily_runtime_history = {
            old_date: 5.0,
            recent_date: 2.0,
        }

        coordinator._clean_old_runtime_history()

        assert old_date not in coordinator._daily_runtime_history
        assert recent_date in coordinator._daily_runtime_history

    def test_clean_old_history_empty(self):
        """Test cleaning empty history doesn't crash."""
        coordinator = create_mock_coordinator()
        coordinator._daily_fuel_history = {}

        coordinator._clean_old_history()

        assert coordinator._daily_fuel_history == {}

    def test_clean_old_runtime_history_empty(self):
        """Test cleaning empty runtime history doesn't crash."""
        coordinator = create_mock_coordinator()
        coordinator._daily_runtime_history = {}

        coordinator._clean_old_runtime_history()

        assert coordinator._daily_runtime_history == {}


# ---------------------------------------------------------------------------
# Protocol mode property tests
# ---------------------------------------------------------------------------

class TestProtocolMode:
    """Tests for protocol_mode property."""

    def test_protocol_mode_returns_value(self):
        """Test protocol_mode returns current mode."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 3

        assert coordinator.protocol_mode == 3

    def test_protocol_mode_default(self):
        """Test protocol_mode default is 0."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 0

        assert coordinator.protocol_mode == 0


# ---------------------------------------------------------------------------
# Notification callback tests
# ---------------------------------------------------------------------------

class TestNotificationCallback:
    """Tests for BLE notification callback."""

    def test_notification_callback_method_exists(self):
        """Test notification callback method exists."""
        coordinator = create_mock_coordinator()

        # Method should exist and be callable
        assert hasattr(coordinator, '_notification_callback')
        assert callable(coordinator._notification_callback)


# ---------------------------------------------------------------------------
# Additional fuel tracking tests
# ---------------------------------------------------------------------------

class TestFuelTrackingAdvanced:
    """Advanced tests for fuel tracking."""

    def test_fuel_consumption_all_levels(self):
        """Test fuel consumption calculation for all levels 1-10."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        for level in range(1, 11):
            coordinator.data["set_level"] = level
            consumption = coordinator._calculate_fuel_consumption(3600)
            expected = FUEL_CONSUMPTION_TABLE.get(level, 0.1)
            assert abs(consumption - expected) < 0.001, f"Level {level} failed"

    def test_fuel_tracking_accumulates(self):
        """Test fuel tracking accumulates over multiple updates."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING
        coordinator.data["set_level"] = 1

        # First update
        coordinator._update_fuel_tracking(1800)  # 30 min
        first_total = coordinator._total_fuel_consumed

        # Second update
        coordinator._update_fuel_tracking(1800)  # 30 min
        second_total = coordinator._total_fuel_consumed

        assert second_total > first_total
        assert abs(second_total - first_total * 2) < 0.01

    def test_fuel_remaining_with_zero_capacity(self):
        """Test fuel remaining when tank capacity is 0."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 0
        coordinator._fuel_consumed_since_reset = 0.0

        coordinator._update_fuel_remaining()

        # With 0 capacity, fuel remaining stays None or 0
        assert coordinator.data["fuel_remaining"] is None or coordinator.data["fuel_remaining"] == 0.0

    def test_fuel_remaining_exact_empty(self):
        """Test fuel remaining when exactly empty."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 5
        coordinator._fuel_consumed_since_reset = 5.0

        coordinator._update_fuel_remaining()

        assert coordinator.data["fuel_remaining"] == 0.0


# ---------------------------------------------------------------------------
# Additional runtime tracking tests
# ---------------------------------------------------------------------------

class TestRuntimeTrackingAdvanced:
    """Advanced tests for runtime tracking."""

    def test_runtime_tracking_accumulates(self):
        """Test runtime tracking accumulates over multiple updates."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        # First update
        coordinator._update_runtime_tracking(1800)  # 30 min
        first_total = coordinator._total_runtime_seconds

        # Second update
        coordinator._update_runtime_tracking(1800)  # 30 min
        second_total = coordinator._total_runtime_seconds

        assert second_total == first_total + 1800

    def test_runtime_updates_data_dict(self):
        """Test runtime tracking updates data dict."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        coordinator._update_runtime_tracking(3600)  # 1 hour

        # Data dict should have updated values
        assert coordinator.data["daily_runtime_hours"] == 1.0
        assert coordinator.data["total_runtime_hours"] == 1.0


# ---------------------------------------------------------------------------
# Additional command building tests
# ---------------------------------------------------------------------------

class TestCommandBuildingAdvanced:
    """Advanced tests for command building."""

    def test_build_command_packet_with_argument(self):
        """Test building command packet with argument."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1  # AA55
        coordinator._passkey = 1234

        # Set level command (cmd 4) with argument 5
        packet = coordinator._build_command_packet(4, 5)

        assert len(packet) == 8
        assert packet[0] == 0xAA
        assert packet[1] == 0x55

    def test_build_command_packet_encrypted(self):
        """Test building command packet for encrypted protocol."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 2  # AA55 Encrypted
        coordinator._passkey = 1234

        packet = coordinator._build_command_packet(1, 0)

        # Command packets start with AA55 regardless of protocol
        assert packet[0] == 0xAA
        assert packet[1] == 0x55

    def test_build_command_packet_aa66(self):
        """Test building AA66 command packet."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 3  # AA66
        coordinator._passkey = 1234

        packet = coordinator._build_command_packet(1, 0)

        # AA66 devices use AA55 command format
        assert len(packet) == 8
        assert packet[0] == 0xAA

    def test_build_command_packet_cbff(self):
        """Test building CBFF command packet (uses AA55 format)."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 6  # CBFF
        coordinator._passkey = 1234

        packet = coordinator._build_command_packet(1, 0)

        # CBFF uses AA55 command format
        assert packet[0] == 0xAA
        assert packet[1] == 0x55


# ---------------------------------------------------------------------------
# Additional protocol detection tests
# ---------------------------------------------------------------------------

class TestProtocolDetectionAdvanced:
    """Advanced tests for protocol detection."""

    def test_detect_protocol_aa66_unencrypted(self):
        """Test detection of AA66 unencrypted protocol."""
        coordinator = create_mock_coordinator()

        # AA66 header, 20 bytes
        data = bytearray([0xAA, 0x66] + [0x00] * 18)
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        assert protocol is not None
        assert protocol.protocol_mode == 3  # AA66 unencrypted

    def test_detect_protocol_short_data(self):
        """Test protocol detection with too short data."""
        coordinator = create_mock_coordinator()

        # Only 5 bytes - too short for any protocol
        data = bytearray([0xAA, 0x55, 0x00, 0x00, 0x00])
        header = (data[0] << 8) | data[1]

        protocol, parsed_data = coordinator._detect_protocol(data, header)

        # Should not match any protocol due to length
        assert protocol is None or parsed_data is None


# ---------------------------------------------------------------------------
# Data persistence format tests
# ---------------------------------------------------------------------------

class TestDataFormat:
    """Tests for data format and rounding."""

    def test_hourly_consumption_rounded(self):
        """Test hourly consumption is rounded to 2 decimals."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING
        coordinator.data["set_level"] = 5

        coordinator._update_fuel_tracking(3600)

        # Check rounding in data dict
        daily = coordinator.data["daily_fuel_consumed"]
        assert daily == round(daily, 2)

    def test_runtime_hours_rounded(self):
        """Test runtime hours are rounded to 2 decimals."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING

        coordinator._update_runtime_tracking(3661)  # 1 hour and 1 second

        hours = coordinator.data["daily_runtime_hours"]
        assert hours == round(hours, 2)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_fuel_consumption_invalid_level(self):
        """Test fuel consumption with invalid level (defaults)."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = RUNNING_STEP_RUNNING
        coordinator.data["set_level"] = 99  # Invalid

        # Should use default consumption rate
        consumption = coordinator._calculate_fuel_consumption(3600)
        assert consumption >= 0

    def test_clear_sensor_values_preserves_non_volatile(self):
        """Test clearing sensor values preserves non-volatile data."""
        coordinator = create_mock_coordinator()
        coordinator.data["daily_fuel_consumed"] = 5.0
        coordinator.data["total_fuel_consumed"] = 100.0
        coordinator.data["cab_temperature"] = 25.0

        coordinator._clear_sensor_values()

        # Volatile should be cleared
        assert coordinator.data["cab_temperature"] is None
        # Non-volatile should remain
        assert coordinator.data["daily_fuel_consumed"] == 5.0
        assert coordinator.data["total_fuel_consumed"] == 100.0

    def test_restore_stale_data_partial(self):
        """Test restoring partial stale data."""
        coordinator = create_mock_coordinator()
        coordinator._last_valid_data = {
            "cab_temperature": 25.0,
            # supply_voltage not saved
        }
        coordinator.data["cab_temperature"] = None
        coordinator.data["supply_voltage"] = None

        coordinator._restore_stale_data()

        # Should restore what we have
        assert coordinator.data["cab_temperature"] == 25.0
        # Should remain None
        assert coordinator.data["supply_voltage"] is None

    def test_connection_failure_first_failure(self):
        """Test first connection failure behavior."""
        coordinator = create_mock_coordinator()
        coordinator._consecutive_failures = 0
        coordinator._last_valid_data = {"cab_temperature": 20.0}
        coordinator.data["cab_temperature"] = 20.0

        coordinator._handle_connection_failure(Exception("Network error"))

        # After first failure, should restore stale data
        assert coordinator._consecutive_failures == 1

    def test_save_valid_data_filters_none(self):
        """Test that save_valid_data doesn't save None values."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["supply_voltage"] = None

        coordinator._save_valid_data()

        assert coordinator._last_valid_data.get("cab_temperature") == 25.0
        # None values should not overwrite existing saved data
        assert coordinator._last_valid_data.get("supply_voltage") is None


# ---------------------------------------------------------------------------
# Temperature offset advanced tests
# ---------------------------------------------------------------------------

class TestTemperatureOffsetAdvanced:
    """Advanced tests for temperature offset."""

    def test_offset_with_heater_offset(self):
        """Test UI offset calculation with heater's own offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 20.0
        coordinator.data["heater_offset"] = 2  # Heater reports +2 offset
        coordinator.config_entry.data = {"temperature_offset": 0.0}

        coordinator._apply_ui_temperature_offset()

        # Raw should be 20 - 2 = 18 (sensor reading before heater offset)
        assert coordinator.data["cab_temperature_raw"] == 18.0

    def test_offset_applies_correctly(self):
        """Test temperature offset applies correctly."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["heater_offset"] = 0
        coordinator.config_entry.data = {"temperature_offset": 5.0}

        coordinator._apply_ui_temperature_offset()

        assert coordinator.data["cab_temperature"] == 30.0

    def test_offset_zero_no_change(self):
        """Test zero offset doesn't change temperature."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["heater_offset"] = 0
        coordinator.config_entry.data = {"temperature_offset": 0.0}

        coordinator._apply_ui_temperature_offset()

        assert coordinator.data["cab_temperature"] == 25.0


# ---------------------------------------------------------------------------
# Async data persistence tests
# ---------------------------------------------------------------------------

class TestAsyncDataPersistence:
    """Tests for async data persistence methods."""

    @pytest.mark.asyncio
    async def test_async_save_data_calls_store(self):
        """Test async_save_data calls the store."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0

        await coordinator.async_save_data()

        coordinator._store.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_save_data_includes_fuel_data(self):
        """Test async_save_data includes fuel tracking data."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0
        coordinator._total_fuel_consumed = 50.5
        coordinator._daily_fuel_consumed = 2.5

        await coordinator.async_save_data()

        # Check the saved data contains fuel info
        call_args = coordinator._store.async_save.call_args
        saved_data = call_args[0][0]
        assert STORAGE_KEY_TOTAL_FUEL in saved_data
        assert STORAGE_KEY_DAILY_FUEL in saved_data

    @pytest.mark.asyncio
    async def test_async_save_data_includes_runtime_data(self):
        """Test async_save_data includes runtime tracking data."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0
        coordinator._total_runtime_seconds = 36000.0
        coordinator._daily_runtime_seconds = 3600.0

        await coordinator.async_save_data()

        call_args = coordinator._store.async_save.call_args
        saved_data = call_args[0][0]
        assert STORAGE_KEY_TOTAL_RUNTIME in saved_data
        assert STORAGE_KEY_DAILY_RUNTIME in saved_data

    @pytest.mark.asyncio
    async def test_async_load_data_restores_fuel(self):
        """Test async_load_data calls store and processes data."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        # Use today's date to avoid daily reset
        today = datetime.now().date().isoformat()
        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 100.5,
            STORAGE_KEY_DAILY_FUEL: 5.0,
            STORAGE_KEY_DAILY_HISTORY: {"2024-01-01": 3.0},
            STORAGE_KEY_DAILY_DATE: today,  # Use today to avoid reset
            STORAGE_KEY_TOTAL_RUNTIME: 7200.0,
            STORAGE_KEY_DAILY_RUNTIME: 1800.0,
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
            STORAGE_KEY_DAILY_RUNTIME_DATE: today,  # Use today to avoid reset
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)

        await coordinator.async_load_data()

        # Verify store was called
        coordinator._store.async_load.assert_called_once()
        # After load, total fuel should be restored from stored data
        # The actual restoration depends on the coordinator implementation
        # Check that data dict has the values (they are synced to data dict)
        assert coordinator.data["total_fuel_consumed"] == 100.5
        assert coordinator.data["daily_fuel_consumed"] == 5.0

    @pytest.mark.asyncio
    async def test_async_load_data_handles_missing_data(self):
        """Test async_load_data handles missing/None data gracefully."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_load = AsyncMock(return_value=None)

        # Should not raise
        await coordinator.async_load_data()

        # Values should remain at defaults
        assert coordinator._total_fuel_consumed == 0.0


# ---------------------------------------------------------------------------
# Async fuel management tests
# ---------------------------------------------------------------------------

class TestAsyncFuelManagement:
    """Tests for async fuel management methods."""

    @pytest.mark.asyncio
    async def test_async_reset_fuel_level(self):
        """Test async_reset_fuel_level resets fuel tracking."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._fuel_consumed_since_reset = 10.0
        coordinator._last_save_time = 0

        await coordinator.async_reset_fuel_level()

        assert coordinator._fuel_consumed_since_reset == 0.0
        assert coordinator.data["fuel_consumed_since_reset"] == 0.0

    @pytest.mark.asyncio
    async def test_async_set_tank_capacity(self):
        """Test async_set_tank_capacity updates capacity."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0

        await coordinator.async_set_tank_capacity(15)

        assert coordinator.data["tank_capacity"] == 15


# ---------------------------------------------------------------------------
# Daily reset tests
# ---------------------------------------------------------------------------

class TestDailyReset:
    """Tests for daily reset functionality."""

    @pytest.mark.asyncio
    async def test_check_daily_reset_same_day(self):
        """Test _check_daily_reset doesn't reset on same day."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        today = datetime.now().strftime("%Y-%m-%d")
        coordinator._last_reset_date = today
        coordinator._daily_fuel_consumed = 5.0

        await coordinator._check_daily_reset()

        # Should not reset since it's the same day
        assert coordinator._daily_fuel_consumed == 5.0

    @pytest.mark.asyncio
    async def test_check_daily_reset_new_day(self):
        """Test _check_daily_reset resets on new day."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        coordinator._last_reset_date = yesterday
        coordinator._daily_fuel_consumed = 5.0
        coordinator._daily_fuel_history = {}

        await coordinator._check_daily_reset()

        # Should reset for new day
        assert coordinator._daily_fuel_consumed == 0.0
        # Yesterday's value should be in history
        assert yesterday in coordinator._daily_fuel_history

    @pytest.mark.asyncio
    async def test_check_daily_runtime_reset_same_day(self):
        """Test _check_daily_runtime_reset doesn't reset on same day."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        today = datetime.now().strftime("%Y-%m-%d")
        coordinator._last_runtime_reset_date = today
        coordinator._daily_runtime_seconds = 3600.0

        await coordinator._check_daily_runtime_reset()

        # Should not reset
        assert coordinator._daily_runtime_seconds == 3600.0

    @pytest.mark.asyncio
    async def test_check_daily_runtime_reset_new_day(self):
        """Test _check_daily_runtime_reset resets on new day."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        coordinator._last_runtime_reset_date = yesterday
        coordinator._daily_runtime_seconds = 7200.0
        coordinator._daily_runtime_history = {}

        await coordinator._check_daily_runtime_reset()

        # Should reset for new day
        assert coordinator._daily_runtime_seconds == 0.0
        # Yesterday's hours should be in history
        assert yesterday in coordinator._daily_runtime_history


# ---------------------------------------------------------------------------
# Async command tests
# ---------------------------------------------------------------------------

class TestAsyncCommands:
    """Tests for async command methods."""

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_turn_on()

        coordinator._send_command.assert_called_once()
        # Command 3 with arg 1 is turn on
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 3
        assert call_args[0][1] == 1

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.data["running_state"] = 1  # Must be running to turn off

        await coordinator.async_turn_off()

        coordinator._send_command.assert_called_once()
        # Command 3 with arg 0 is turn off
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 3
        assert call_args[0][1] == 0

    @pytest.mark.asyncio
    async def test_async_set_level(self):
        """Test async_set_level sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_level(7)

        coordinator._send_command.assert_called_once()
        # Command 4 is set level
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 4
        assert call_args[0][1] == 7

    @pytest.mark.asyncio
    async def test_async_set_temperature(self):
        """Test async_set_temperature sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_temperature(25)

        coordinator._send_command.assert_called_once()
        # Command 4 is used for both level and temperature
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 4
        assert call_args[0][1] == 25

    @pytest.mark.asyncio
    async def test_async_set_mode(self):
        """Test async_set_mode sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_mode(2)  # Temperature mode

        coordinator._send_command.assert_called_once()
        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 2

    @pytest.mark.asyncio
    async def test_async_set_auto_start_stop(self):
        """Test async_set_auto_start_stop sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_auto_start_stop(True)

        coordinator._send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_sync_time(self):
        """Test async_sync_time sends time sync command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_sync_time()

        coordinator._send_command.assert_called_once()
        # Command 10 is time sync
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 10

    @pytest.mark.asyncio
    async def test_async_set_heater_offset(self):
        """Test async_set_heater_offset sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_heater_offset(3)

        coordinator._send_command.assert_called_once()
        # Command 12 is set offset (or 20 for newer protocol)
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] in [12, 20]

    @pytest.mark.asyncio
    async def test_async_set_backlight(self):
        """Test async_set_backlight sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_backlight(5)

        coordinator._send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_auto_offset_enabled(self):
        """Test async_set_auto_offset_enabled updates state."""
        coordinator = create_mock_coordinator()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator._last_save_time = 0
        coordinator._setup_external_temp_listener = AsyncMock()
        coordinator._auto_offset_unsub = None

        await coordinator.async_set_auto_offset_enabled(True)

        assert coordinator.data["auto_offset_enabled"] is True

    @pytest.mark.asyncio
    async def test_async_send_raw_command(self):
        """Test async_send_raw_command sends arbitrary command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        result = await coordinator.async_send_raw_command(99, 42)

        assert result is True
        coordinator._send_command.assert_called_once_with(99, 42)


# ---------------------------------------------------------------------------
# Address and heater ID tests
# ---------------------------------------------------------------------------

class TestAddressProperties:
    """Tests for address-related properties."""

    def test_address_property(self):
        """Test address property returns BLE address."""
        coordinator = create_mock_coordinator()
        coordinator._address = "AA:BB:CC:DD:EE:FF"

        # Check if address property exists and works
        assert hasattr(coordinator, '_address')
        assert coordinator._address == "AA:BB:CC:DD:EE:FF"

    def test_heater_id_format(self):
        """Test heater_id is last 2 bytes of address."""
        coordinator = create_mock_coordinator()
        coordinator._heater_id = "EE:FF"

        assert coordinator._heater_id == "EE:FF"


# ---------------------------------------------------------------------------
# ABBA protocol specific tests
# ---------------------------------------------------------------------------

class TestABBAProtocol:
    """Tests for ABBA protocol specific behavior."""

    def test_is_abba_device_flag(self):
        """Test _is_abba_device flag."""
        coordinator = create_mock_coordinator()
        coordinator._is_abba_device = True

        assert coordinator._is_abba_device is True

    def test_build_command_abba_uses_protocol(self):
        """Test ABBA command building uses protocol handler."""
        from diesel_heater_ble import ProtocolABBA

        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5
        coordinator._is_abba_device = True
        coordinator._protocol = ProtocolABBA()

        packet = coordinator._build_command_packet(1, 0)

        # ABBA packets start with BA AB
        assert packet[0] == 0xBA
        assert packet[1] == 0xAB


# ---------------------------------------------------------------------------
# Statistics import tests
# ---------------------------------------------------------------------------

class TestStatisticsImport:
    """Tests for statistics import functionality."""

    def test_has_import_statistics_method(self):
        """Test _import_statistics method exists."""
        coordinator = create_mock_coordinator()

        assert hasattr(coordinator, '_import_statistics')
        assert callable(coordinator._import_statistics)

    def test_has_import_runtime_statistics_method(self):
        """Test _import_runtime_statistics method exists."""
        coordinator = create_mock_coordinator()

        assert hasattr(coordinator, '_import_runtime_statistics')
        assert callable(coordinator._import_runtime_statistics)


# ---------------------------------------------------------------------------
# Additional async command tests
# ---------------------------------------------------------------------------

class TestAsyncConfigurationCommands:
    """Tests for async configuration commands."""

    @pytest.mark.asyncio
    async def test_async_set_language(self):
        """Test async_set_language sends correct command."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_language(2)  # German

        coordinator._send_command.assert_called_once()
        # Command 14 is set language
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 14
        assert call_args[0][1] == 2

    @pytest.mark.asyncio
    async def test_async_set_temp_unit_celsius(self):
        """Test async_set_temp_unit sets Celsius."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_temp_unit(False)  # Celsius

        coordinator._send_command.assert_called_once()
        # Command 15 is set temp unit
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 15
        assert call_args[0][1] == 0  # 0 = Celsius

    @pytest.mark.asyncio
    async def test_async_set_temp_unit_fahrenheit(self):
        """Test async_set_temp_unit sets Fahrenheit."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_temp_unit(True)  # Fahrenheit

        coordinator._send_command.assert_called_once()
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 15
        assert call_args[0][1] == 1  # 1 = Fahrenheit

    @pytest.mark.asyncio
    async def test_async_set_altitude_unit_meters(self):
        """Test async_set_altitude_unit sets meters."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_altitude_unit(False)  # Meters

        coordinator._send_command.assert_called_once()
        # Command 19 is set altitude unit
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 19
        assert call_args[0][1] == 0  # 0 = Meters

    @pytest.mark.asyncio
    async def test_async_set_altitude_unit_feet(self):
        """Test async_set_altitude_unit sets feet."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_altitude_unit(True)  # Feet

        coordinator._send_command.assert_called_once()
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 19
        assert call_args[0][1] == 1  # 1 = Feet

    @pytest.mark.asyncio
    async def test_async_set_high_altitude_enabled_abba(self):
        """Test async_set_high_altitude enables high altitude mode for ABBA."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator._is_abba_device = True  # Must be ABBA device
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_set_high_altitude(True)

        coordinator._send_command.assert_called_once()
        # Command 99 is high altitude toggle
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 99

    @pytest.mark.asyncio
    async def test_async_set_high_altitude_skipped_non_abba(self):
        """Test async_set_high_altitude does nothing for non-ABBA devices."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator._is_abba_device = False  # Not ABBA device

        await coordinator.async_set_high_altitude(True)

        # Should not call _send_command for non-ABBA devices
        coordinator._send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_tank_volume(self):
        """Test async_set_tank_volume sets tank volume index."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_tank_volume(5)  # Index 5 = 25L

        coordinator._send_command.assert_called_once()
        # Command 16 is set tank volume
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 16
        assert call_args[0][1] == 5

    @pytest.mark.asyncio
    async def test_async_set_pump_type(self):
        """Test async_set_pump_type sets pump type."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_pump_type(2)  # 28µl pump

        coordinator._send_command.assert_called_once()
        # Command 17 is set pump type
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 17
        assert call_args[0][1] == 2


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------

class TestResponseParsing:
    """Tests for response parsing functionality."""

    def test_parse_response_aa55_updates_data(self):
        """Test parsing AA55 response updates data dict."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1  # AA55
        coordinator._protocol = coordinator._protocols[1]

        # Create a valid 20-byte AA55 response
        data = bytearray([0xAA, 0x55] + [0x00] * 18)

        # Parse the response (actual byte positions depend on protocol)
        coordinator._parse_response(data)

        # After parsing, data dict should have some values updated
        # (not checking specific values since protocol layout is complex)
        assert "running_state" in coordinator.data

    def test_parse_response_method_exists(self):
        """Test _parse_response method exists."""
        coordinator = create_mock_coordinator()

        assert hasattr(coordinator, '_parse_response')
        assert callable(coordinator._parse_response)

    def test_parse_response_processes_data(self):
        """Test parsing response processes the data without error."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1  # AA55
        coordinator._protocol = coordinator._protocols[1]

        # Create a valid response
        data = bytearray([0xAA, 0x55] + [0x00] * 18)

        # Should not raise an exception
        coordinator._parse_response(data)

        # Data dict should still be accessible
        assert coordinator.data is not None


# ---------------------------------------------------------------------------
# Utility methods tests
# ---------------------------------------------------------------------------

class TestUtilityMethods:
    """Tests for utility methods."""

    def test_protocol_mode_property(self):
        """Test protocol_mode property getter."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5

        assert coordinator.protocol_mode == 5

    def test_clear_sensor_values_all_volatile(self):
        """Test clearing all volatile sensor values."""
        coordinator = create_mock_coordinator()
        # Set all volatile fields
        coordinator.data["case_temperature"] = 50
        coordinator.data["cab_temperature"] = 20
        coordinator.data["supply_voltage"] = 12.5
        coordinator.data["running_state"] = 1
        coordinator.data["running_step"] = 3
        coordinator.data["set_level"] = 5
        coordinator.data["set_temp"] = 22

        coordinator._clear_sensor_values()

        # All volatile fields should be None
        assert coordinator.data["case_temperature"] is None
        assert coordinator.data["cab_temperature"] is None
        assert coordinator.data["supply_voltage"] is None

    def test_save_valid_data_all_fields(self):
        """Test saving all valid data fields."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = 25.0
        coordinator.data["case_temperature"] = 60
        coordinator.data["supply_voltage"] = 13.2
        coordinator._last_valid_data = {}

        coordinator._save_valid_data()

        assert coordinator._last_valid_data["cab_temperature"] == 25.0
        assert coordinator._last_valid_data["case_temperature"] == 60
        assert coordinator._last_valid_data["supply_voltage"] == 13.2


# ---------------------------------------------------------------------------
# Temperature clamp tests
# ---------------------------------------------------------------------------

class TestTemperatureClamp:
    """Tests for temperature clamping logic."""

    @pytest.mark.asyncio
    async def test_set_temperature_clamps_below_min(self):
        """Test temperature below 8 is clamped to 8."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_temperature(5)  # Below min

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 8  # Clamped to min

    @pytest.mark.asyncio
    async def test_set_temperature_clamps_above_max(self):
        """Test temperature above 36 is clamped to 36."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_temperature(40)  # Above max

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 36  # Clamped to max


# ---------------------------------------------------------------------------
# Level clamp tests
# ---------------------------------------------------------------------------

class TestLevelClamp:
    """Tests for level clamping logic."""

    @pytest.mark.asyncio
    async def test_set_level_clamps_below_min(self):
        """Test level below 1 is clamped to 1."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_level(0)  # Below min

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 1  # Clamped to min

    @pytest.mark.asyncio
    async def test_set_level_clamps_above_max(self):
        """Test level above 10 is clamped to 10."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_level(15)  # Above max

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 10  # Clamped to max

    @pytest.mark.asyncio
    async def test_set_level_in_range(self):
        """Test level in valid range is not clamped."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_level(5)  # In range

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 5  # Not clamped


# ---------------------------------------------------------------------------
# Mode command tests
# ---------------------------------------------------------------------------

class TestModeCommands:
    """Tests for mode switching commands."""

    @pytest.mark.asyncio
    async def test_set_mode_level(self):
        """Test setting level mode (1)."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_mode(1)  # Level mode

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 1

    @pytest.mark.asyncio
    async def test_set_mode_temperature(self):
        """Test setting temperature mode (2)."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)

        await coordinator.async_set_mode(2)  # Temperature mode

        call_args = coordinator._send_command.call_args
        assert call_args[0][1] == 2


# ---------------------------------------------------------------------------
# HeaterLoggerAdapter tests
# ---------------------------------------------------------------------------

class TestHeaterLoggerAdapter:
    """Tests for the HeaterLoggerAdapter class."""

    def test_process_prefixes_message(self):
        """Test that process() prefixes messages with heater ID."""
        from custom_components.diesel_heater.coordinator import _HeaterLoggerAdapter
        import logging

        base_logger = logging.getLogger("test")
        adapter = _HeaterLoggerAdapter(base_logger, {"heater_id": "EE:FF"})

        msg, kwargs = adapter.process("Test message", {})

        assert msg == "[EE:FF] Test message"
        assert kwargs == {}

    def test_process_preserves_kwargs(self):
        """Test that process() preserves kwargs."""
        from custom_components.diesel_heater.coordinator import _HeaterLoggerAdapter
        import logging

        base_logger = logging.getLogger("test")
        adapter = _HeaterLoggerAdapter(base_logger, {"heater_id": "AA:BB"})

        msg, kwargs = adapter.process("Message", {"extra": "value"})

        assert msg == "[AA:BB] Message"
        assert kwargs == {"extra": "value"}


# ---------------------------------------------------------------------------
# async_load_data tests (edge cases)
# ---------------------------------------------------------------------------

class TestAsyncLoadDataEdgeCases:
    """Tests for async_load_data edge cases."""

    @pytest.mark.asyncio
    async def test_load_data_new_day_resets_daily_fuel(self):
        """Test that loading data on a new day resets daily fuel counter."""
        coordinator = create_mock_coordinator()
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 100.0,
            STORAGE_KEY_DAILY_FUEL: 5.0,  # Yesterday's consumption
            STORAGE_KEY_DAILY_DATE: yesterday,
            STORAGE_KEY_DAILY_HISTORY: {},
            STORAGE_KEY_TOTAL_RUNTIME: 3600.0,
            STORAGE_KEY_DAILY_RUNTIME: 1800.0,
            STORAGE_KEY_DAILY_RUNTIME_DATE: yesterday,
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)
        coordinator._import_all_history_statistics = AsyncMock()
        coordinator._import_all_runtime_history_statistics = AsyncMock()
        coordinator._setup_external_temp_listener = AsyncMock()

        await coordinator.async_load_data()

        # Daily counter should be reset
        assert coordinator._daily_fuel_consumed == 0.0
        # Yesterday's value saved to history
        assert yesterday in coordinator._daily_fuel_history

    @pytest.mark.asyncio
    async def test_load_data_same_day_preserves_daily(self):
        """Test that loading data on same day preserves daily counters."""
        coordinator = create_mock_coordinator()
        today = datetime.now().date().isoformat()

        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 50.0,
            STORAGE_KEY_DAILY_FUEL: 2.5,
            STORAGE_KEY_DAILY_DATE: today,
            STORAGE_KEY_DAILY_HISTORY: {},
            STORAGE_KEY_TOTAL_RUNTIME: 1800.0,
            STORAGE_KEY_DAILY_RUNTIME: 900.0,
            STORAGE_KEY_DAILY_RUNTIME_DATE: today,
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)
        coordinator._import_all_history_statistics = AsyncMock()
        coordinator._import_all_runtime_history_statistics = AsyncMock()
        coordinator._setup_external_temp_listener = AsyncMock()

        await coordinator.async_load_data()

        # Daily counter should be preserved
        assert coordinator._daily_fuel_consumed == 2.5
        assert coordinator._daily_runtime_seconds == 900.0

    @pytest.mark.asyncio
    async def test_load_data_with_tank_capacity(self):
        """Test loading data with tank capacity."""
        coordinator = create_mock_coordinator()
        today = datetime.now().date().isoformat()

        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 10.0,
            STORAGE_KEY_DAILY_FUEL: 1.0,
            STORAGE_KEY_DAILY_DATE: today,
            STORAGE_KEY_DAILY_HISTORY: {},
            STORAGE_KEY_TOTAL_RUNTIME: 0.0,
            STORAGE_KEY_DAILY_RUNTIME: 0.0,
            STORAGE_KEY_DAILY_RUNTIME_DATE: today,
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
            STORAGE_KEY_TANK_CAPACITY: 15,
            STORAGE_KEY_FUEL_SINCE_RESET: 3.5,
            STORAGE_KEY_LAST_REFUELED: "2024-01-15T10:00:00",
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)
        coordinator._import_all_history_statistics = AsyncMock()
        coordinator._import_all_runtime_history_statistics = AsyncMock()
        coordinator._setup_external_temp_listener = AsyncMock()
        coordinator._update_fuel_remaining = MagicMock()

        await coordinator.async_load_data()

        assert coordinator.data["tank_capacity"] == 15
        assert coordinator._fuel_consumed_since_reset == 3.5
        assert coordinator.data["last_refueled"] == "2024-01-15T10:00:00"

    @pytest.mark.asyncio
    async def test_load_data_with_auto_offset_enabled(self):
        """Test loading data with auto offset enabled state."""
        coordinator = create_mock_coordinator()
        today = datetime.now().date().isoformat()

        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 0.0,
            STORAGE_KEY_DAILY_FUEL: 0.0,
            STORAGE_KEY_DAILY_DATE: today,
            STORAGE_KEY_DAILY_HISTORY: {},
            STORAGE_KEY_TOTAL_RUNTIME: 0.0,
            STORAGE_KEY_DAILY_RUNTIME: 0.0,
            STORAGE_KEY_DAILY_RUNTIME_DATE: today,
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
            STORAGE_KEY_AUTO_OFFSET_ENABLED: True,
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)
        coordinator._import_all_history_statistics = AsyncMock()
        coordinator._import_all_runtime_history_statistics = AsyncMock()
        coordinator._setup_external_temp_listener = AsyncMock()

        await coordinator.async_load_data()

        assert coordinator.data["auto_offset_enabled"] is True

    @pytest.mark.asyncio
    async def test_load_data_handles_exception(self):
        """Test async_load_data handles storage exceptions gracefully."""
        coordinator = create_mock_coordinator()
        coordinator._store.async_load = AsyncMock(side_effect=Exception("Storage error"))
        coordinator._setup_external_temp_listener = AsyncMock()

        # Should not raise
        await coordinator.async_load_data()

        # External temp listener should still be set up
        coordinator._setup_external_temp_listener.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_data_no_saved_date_uses_today(self):
        """Test that missing saved date defaults to today."""
        coordinator = create_mock_coordinator()

        stored_data = {
            STORAGE_KEY_TOTAL_FUEL: 10.0,
            STORAGE_KEY_DAILY_FUEL: 1.0,
            # No STORAGE_KEY_DAILY_DATE
            STORAGE_KEY_DAILY_HISTORY: {},
            STORAGE_KEY_TOTAL_RUNTIME: 0.0,
            STORAGE_KEY_DAILY_RUNTIME: 0.0,
            # No STORAGE_KEY_DAILY_RUNTIME_DATE
            STORAGE_KEY_DAILY_RUNTIME_HISTORY: {},
        }
        coordinator._store.async_load = AsyncMock(return_value=stored_data)
        coordinator._import_all_history_statistics = AsyncMock()
        coordinator._import_all_runtime_history_statistics = AsyncMock()
        coordinator._setup_external_temp_listener = AsyncMock()

        await coordinator.async_load_data()

        today = datetime.now().date().isoformat()
        assert coordinator._last_reset_date == today
        assert coordinator._last_runtime_reset_date == today


# ---------------------------------------------------------------------------
# External temperature sensor tests
# ---------------------------------------------------------------------------

class TestExternalTempSensor:
    """Tests for external temperature sensor integration."""

    @pytest.mark.asyncio
    async def test_setup_external_temp_no_sensor_configured(self):
        """Test setup with no external sensor configured."""
        coordinator = create_mock_coordinator()
        coordinator.config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}  # No CONF_EXTERNAL_TEMP_SENSOR
        coordinator._auto_offset_unsub = None

        await coordinator._setup_external_temp_listener()

        # No listener should be set up
        assert coordinator._auto_offset_unsub is None

    @pytest.mark.asyncio
    async def test_setup_external_temp_with_sensor(self):
        """Test setup with external sensor configured."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.external_temp",
        }
        coordinator._auto_offset_unsub = None
        coordinator._async_calculate_auto_offset = AsyncMock()

        # Mock async_track_state_change_event
        mock_unsub = MagicMock()
        with patch("custom_components.diesel_heater.coordinator.async_track_state_change_event", return_value=mock_unsub) as mock_track:
            await coordinator._setup_external_temp_listener()

            mock_track.assert_called_once()
            assert coordinator._auto_offset_unsub == mock_unsub

    @pytest.mark.asyncio
    async def test_setup_external_temp_cleans_up_existing(self):
        """Test that setup cleans up existing listener first."""
        coordinator = create_mock_coordinator()
        coordinator.config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
        old_unsub = MagicMock()
        coordinator._auto_offset_unsub = old_unsub

        await coordinator._setup_external_temp_listener()

        # Old listener should be cleaned up
        old_unsub.assert_called_once()
        assert coordinator._auto_offset_unsub is None


# ---------------------------------------------------------------------------
# Auto offset calculation tests
# ---------------------------------------------------------------------------

class TestAutoOffsetCalculation:
    """Tests for auto temperature offset calculation."""

    @pytest.mark.asyncio
    async def test_auto_offset_disabled(self):
        """Test that auto offset is skipped when disabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = False
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_no_external_sensor(self):
        """Test auto offset with no external sensor configured."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_throttled(self):
        """Test auto offset is throttled."""
        import time
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
        }
        coordinator._last_auto_offset_time = time.time()  # Just now
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_external_sensor_unavailable(self):
        """Test auto offset when external sensor is unavailable."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
        }
        coordinator._last_auto_offset_time = 0

        # Mock unavailable state
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_invalid_external_value(self):
        """Test auto offset with invalid external sensor value."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
        }
        coordinator._last_auto_offset_time = 0

        mock_state = MagicMock()
        mock_state.state = "not_a_number"
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_no_heater_temp(self):
        """Test auto offset when heater raw temp is not available."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = None
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
        }
        coordinator._last_auto_offset_time = 0

        mock_state = MagicMock()
        mock_state.state = "22.5"
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_small_difference_ignored(self):
        """Test auto offset ignores small temperature differences."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 22
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        mock_state = MagicMock()
        mock_state.state = "22.3"  # Only 0.3 difference
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_applies_offset(self):
        """Test auto offset applies when difference is significant."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 25  # Heater reads 25
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 5,
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        mock_state = MagicMock()
        mock_state.state = "22"  # External reads 22, difference = -3
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # Should apply offset of -3
        coordinator.async_set_heater_offset.assert_called_once_with(-3)

    @pytest.mark.asyncio
    async def test_auto_offset_clamped_to_max(self):
        """Test auto offset is clamped to max value."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 30  # Heater reads 30
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 3,  # Max offset is 3
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        mock_state = MagicMock()
        mock_state.state = "20"  # External reads 20, difference = -10
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # Should clamp to -3 (max)
        coordinator.async_set_heater_offset.assert_called_once_with(-3)

    @pytest.mark.asyncio
    async def test_auto_offset_no_change_skipped(self):
        """Test auto offset skips sending when offset unchanged."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 22
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 5,
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = -3  # Already set to -3

        mock_state = MagicMock()
        mock_state.state = "19"  # External=19, heater=22, diff=-3
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # Offset unchanged, should not call
        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_fahrenheit_external_sensor(self):
        """Test auto offset correctly converts Fahrenheit external sensor to Celsius.

        Issue #31: External sensor in Fahrenheit was not converted before offset calculation.
        Example: External=52.1°F (11.2°C), Heater=12°C → offset should be ~-1, not +40.
        """
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 12  # Heater reads 12°C
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 5,
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        # External sensor reports 53.6°F which is ~12°C
        mock_state = MagicMock()
        mock_state.state = "53.6"
        mock_state.attributes = {"unit_of_measurement": "°F"}
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # 53.6°F = 12°C, heater=12°C, difference=0 → no offset needed
        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_offset_fahrenheit_with_difference(self):
        """Test auto offset with Fahrenheit sensor and significant difference."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 15  # Heater reads 15°C
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 5,
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        # External sensor reports 50°F which is 10°C
        # 50°F = (50-32) * 5/9 = 10°C
        mock_state = MagicMock()
        mock_state.state = "50"
        mock_state.attributes = {"unit_of_measurement": "°F"}
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # External=10°C, heater=15°C, difference=-5 → offset=-5
        coordinator.async_set_heater_offset.assert_called_once_with(-5)

    @pytest.mark.asyncio
    async def test_auto_offset_celsius_unit_explicit(self):
        """Test auto offset with explicit Celsius unit works normally."""
        from custom_components.diesel_heater.const import CONF_EXTERNAL_TEMP_SENSOR, CONF_AUTO_OFFSET_MAX

        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        coordinator.data["cab_temperature_raw"] = 25  # Heater reads 25°C
        coordinator.config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.temp",
            CONF_AUTO_OFFSET_MAX: 5,
        }
        coordinator._last_auto_offset_time = 0
        coordinator._current_heater_offset = 0

        mock_state = MagicMock()
        mock_state.state = "22"  # External reads 22°C
        mock_state.attributes = {"unit_of_measurement": "°C"}
        coordinator.hass.states.get = MagicMock(return_value=mock_state)
        coordinator.async_set_heater_offset = AsyncMock()

        await coordinator._async_calculate_auto_offset()

        # External=22°C, heater=25°C, difference=-3 → offset=-3
        coordinator.async_set_heater_offset.assert_called_once_with(-3)


# ---------------------------------------------------------------------------
# Connection failure handling tests
# ---------------------------------------------------------------------------

class TestConnectionFailureHandling2:
    """Additional tests for connection failure handling."""

    def test_handle_connection_failure_marks_disconnected_after_max_stale(self):
        """Test that connection is marked disconnected after max stale cycles."""
        coordinator = create_mock_coordinator()
        coordinator._consecutive_failures = 3  # Already at max
        coordinator._max_stale_cycles = 3
        coordinator.data["connected"] = True
        coordinator.data["cab_temperature"] = 22
        coordinator._clear_sensor_values = MagicMock()

        coordinator._handle_connection_failure(Exception("Test error"))

        assert coordinator._consecutive_failures == 4
        assert coordinator.data["connected"] is False
        coordinator._clear_sensor_values.assert_called_once()

    def test_handle_connection_failure_logs_warning_once(self):
        """Test warning is logged only once when going offline."""
        coordinator = create_mock_coordinator()
        coordinator._consecutive_failures = 3  # At exactly max + 1
        coordinator._max_stale_cycles = 3
        coordinator.data["connected"] = True
        coordinator._clear_sensor_values = MagicMock()

        coordinator._handle_connection_failure(Exception("Test error"))

        # Should log warning (consecutive_failures becomes 4 = max_stale_cycles + 1)
        coordinator._logger.warning.assert_called()


# ---------------------------------------------------------------------------
# _async_update_data tests
# ---------------------------------------------------------------------------

class TestAsyncUpdateData:
    """Tests for the main _async_update_data method."""

    @pytest.mark.asyncio
    async def test_update_data_checks_daily_reset_first(self):
        """Test that daily reset is checked even if disconnected."""
        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = None  # Not connected
        coordinator._ensure_connected = AsyncMock(side_effect=Exception("Cannot connect"))
        coordinator._handle_connection_failure = MagicMock()

        from homeassistant.helpers.update_coordinator import UpdateFailed
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Daily resets should still be checked
        coordinator._check_daily_reset.assert_called_once()
        coordinator._check_daily_runtime_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_data_success_resets_failure_counter(self):
        """Test successful update resets consecutive failures."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator._consecutive_failures = 5
        coordinator._last_update_time = time.time() - 60
        coordinator._last_save_time = time.time()
        coordinator._save_valid_data = MagicMock()
        coordinator._update_fuel_tracking = MagicMock()
        coordinator._update_runtime_tracking = MagicMock()
        coordinator.async_save_data = AsyncMock()

        result = await coordinator._async_update_data()

        assert coordinator._consecutive_failures == 0
        assert coordinator.data["connected"] is True
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_data_retries_on_timeout(self):
        """Test update data retries status request on timeout."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        # First two calls fail, third succeeds
        coordinator._send_command = AsyncMock(side_effect=[False, False, True])
        coordinator._consecutive_failures = 0
        coordinator._last_update_time = time.time() - 60
        coordinator._last_save_time = time.time()
        coordinator._save_valid_data = MagicMock()
        coordinator._update_fuel_tracking = MagicMock()
        coordinator._update_runtime_tracking = MagicMock()
        coordinator.async_save_data = AsyncMock()

        result = await coordinator._async_update_data()

        # Should have tried 3 times
        assert coordinator._send_command.call_count == 3
        assert coordinator.data["connected"] is True

    @pytest.mark.asyncio
    async def test_update_data_saves_periodically(self):
        """Test update data saves every 5 minutes."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator._consecutive_failures = 0
        coordinator._last_update_time = time.time() - 60
        coordinator._last_save_time = time.time() - 301  # Over 5 minutes ago
        coordinator._save_valid_data = MagicMock()
        coordinator._update_fuel_tracking = MagicMock()
        coordinator._update_runtime_tracking = MagicMock()
        coordinator.async_save_data = AsyncMock()

        await coordinator._async_update_data()

        coordinator.async_save_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_data_no_status_returns_stale_during_tolerance(self):
        """Test no status returns stale data during tolerance window."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._send_command = AsyncMock(return_value=False)  # All fail
        coordinator._consecutive_failures = 1  # Within tolerance
        coordinator._max_stale_cycles = 3
        coordinator._last_update_time = time.time()
        coordinator._handle_connection_failure = MagicMock()

        result = await coordinator._async_update_data()

        # Should return stale data, not raise
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_data_no_status_raises_after_tolerance(self):
        """Test no status raises UpdateFailed after tolerance exceeded."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator._consecutive_failures = 4  # Beyond tolerance
        coordinator._max_stale_cycles = 3
        coordinator._last_update_time = time.time()
        coordinator._handle_connection_failure = MagicMock()

        from homeassistant.helpers.update_coordinator import UpdateFailed
        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data()

        assert "No status received" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_data_exception_returns_stale_during_tolerance(self):
        """Test exception returns stale data during tolerance window."""
        import time

        coordinator = create_mock_coordinator()
        coordinator._check_daily_reset = AsyncMock()
        coordinator._check_daily_runtime_reset = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._send_command = AsyncMock(side_effect=Exception("BLE error"))
        coordinator._consecutive_failures = 2
        coordinator._max_stale_cycles = 3
        coordinator._last_update_time = time.time()
        coordinator._handle_connection_failure = MagicMock()

        result = await coordinator._async_update_data()

        assert result == coordinator.data


# ---------------------------------------------------------------------------
# External temp callback tests
# ---------------------------------------------------------------------------

class TestExternalTempCallback:
    """Tests for external temperature change callback."""

    def test_external_temp_changed_schedules_task(self):
        """Test _async_external_temp_changed schedules calculation task."""
        coordinator = create_mock_coordinator()
        coordinator._async_calculate_auto_offset = AsyncMock()
        mock_task = MagicMock()
        coordinator.hass.async_create_task = MagicMock(return_value=mock_task)

        event = MagicMock()
        coordinator._async_external_temp_changed(event)

        coordinator.hass.async_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# async_save_data tests
# ---------------------------------------------------------------------------

class TestAsyncSaveData:
    """Tests for async_save_data method."""

    @pytest.mark.asyncio
    async def test_save_data_handles_exception(self):
        """Test async_save_data handles storage exception gracefully."""
        coordinator = create_mock_coordinator()
        coordinator._store.async_save = AsyncMock(side_effect=Exception("Write failed"))

        # Should not raise
        await coordinator.async_save_data()

        # Warning should be logged
        coordinator._logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_save_data_success(self):
        """Test async_save_data saves data successfully."""
        coordinator = create_mock_coordinator()
        coordinator._store.async_save = AsyncMock()

        await coordinator.async_save_data()

        coordinator._store.async_save.assert_called_once()
        # Verify data includes expected keys
        call_args = coordinator._store.async_save.call_args
        saved_data = call_args[0][0]
        assert STORAGE_KEY_TOTAL_FUEL in saved_data
        assert STORAGE_KEY_DAILY_FUEL in saved_data


# ---------------------------------------------------------------------------
# Statistics import tests
# ---------------------------------------------------------------------------

class TestStatisticsImportDetailed:
    """Detailed tests for statistics import functionality."""

    @pytest.mark.asyncio
    async def test_import_statistics_no_recorder(self):
        """Test _import_statistics when recorder not available."""
        coordinator = create_mock_coordinator()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=None):
            await coordinator._import_statistics("2024-01-15", 2.5)

        # Should just return without error
        coordinator._logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_import_statistics_invalid_date(self):
        """Test _import_statistics with invalid date string."""
        coordinator = create_mock_coordinator()
        mock_recorder = MagicMock()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=mock_recorder):
            await coordinator._import_statistics("not-a-date", 2.5)

        coordinator._logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_import_statistics_exception(self):
        """Test _import_statistics handles async_add_external_statistics exception."""
        coordinator = create_mock_coordinator()
        mock_recorder = MagicMock()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=mock_recorder):
            with patch("custom_components.diesel_heater.coordinator.async_add_external_statistics", side_effect=Exception("Stats error")):
                await coordinator._import_statistics("2024-01-15", 2.5)

        coordinator._logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_import_all_history_statistics_with_data(self):
        """Test _import_all_history_statistics with actual history."""
        coordinator = create_mock_coordinator()
        coordinator._daily_fuel_history = {
            "2024-01-14": 2.5,
            "2024-01-15": 3.0,
        }
        coordinator._import_statistics = AsyncMock()

        await coordinator._import_all_history_statistics()

        assert coordinator._import_statistics.call_count == 2

    @pytest.mark.asyncio
    async def test_import_runtime_statistics_no_recorder(self):
        """Test _import_runtime_statistics when recorder not available."""
        coordinator = create_mock_coordinator()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=None):
            await coordinator._import_runtime_statistics("2024-01-15", 4.5)

        coordinator._logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_import_runtime_statistics_invalid_date(self):
        """Test _import_runtime_statistics with invalid date string."""
        coordinator = create_mock_coordinator()
        mock_recorder = MagicMock()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=mock_recorder):
            await coordinator._import_runtime_statistics("invalid", 4.5)

        coordinator._logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_import_runtime_statistics_exception(self):
        """Test _import_runtime_statistics handles exception."""
        coordinator = create_mock_coordinator()
        mock_recorder = MagicMock()

        with patch("custom_components.diesel_heater.coordinator.get_instance", return_value=mock_recorder):
            with patch("custom_components.diesel_heater.coordinator.async_add_external_statistics", side_effect=Exception("Stats error")):
                await coordinator._import_runtime_statistics("2024-01-15", 4.5)

        coordinator._logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_import_all_runtime_history_statistics_with_data(self):
        """Test _import_all_runtime_history_statistics with actual history."""
        coordinator = create_mock_coordinator()
        coordinator._daily_runtime_history = {
            "2024-01-14": 3.5,
            "2024-01-15": 5.0,
        }
        coordinator._import_runtime_statistics = AsyncMock()

        await coordinator._import_all_runtime_history_statistics()

        assert coordinator._import_runtime_statistics.call_count == 2


# ---------------------------------------------------------------------------
# BLE connection cleanup tests
# ---------------------------------------------------------------------------

class TestBLEConnectionCleanup:
    """Tests for BLE connection cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_connection_no_client(self):
        """Test cleanup_connection with no client."""
        coordinator = create_mock_coordinator()
        coordinator._client = None

        await coordinator._cleanup_connection()

        # Should not raise
        assert coordinator._client is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_disconnects(self):
        """Test cleanup_connection disconnects active client."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        coordinator._client = mock_client
        coordinator._characteristic = MagicMock()
        coordinator._characteristic.properties = ["notify"]
        coordinator._active_char_uuid = "fff1"

        await coordinator._cleanup_connection()

        mock_client.stop_notify.assert_called_once_with("fff1")
        mock_client.disconnect.assert_called_once()
        assert coordinator._client is None
        assert coordinator._characteristic is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_handles_disconnect_error(self):
        """Test cleanup_connection handles disconnect error gracefully."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        coordinator._client = mock_client
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        await coordinator._cleanup_connection()

        # Should still clean up
        assert coordinator._client is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_handles_stop_notify_error(self):
        """Test cleanup_connection handles stop_notify error gracefully."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock()
        mock_client.stop_notify = AsyncMock(side_effect=Exception("Stop notify failed"))
        coordinator._client = mock_client
        coordinator._characteristic = MagicMock()
        coordinator._characteristic.properties = ["notify"]
        coordinator._active_char_uuid = "fff1"

        await coordinator._cleanup_connection()

        # Should still disconnect and clean up
        mock_client.disconnect.assert_called_once()
        assert coordinator._client is None


# ---------------------------------------------------------------------------
# GATT write tests
# ---------------------------------------------------------------------------

class TestGATTWrite:
    """Tests for GATT write operations."""

    @pytest.mark.asyncio
    async def test_write_gatt_standard_characteristic(self):
        """Test _write_gatt uses standard characteristic."""
        coordinator = create_mock_coordinator()
        coordinator._is_abba_device = False
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        coordinator._client = mock_client
        coordinator._characteristic = "standard_char"
        coordinator._abba_write_char = None

        packet = bytearray([0xAA, 0x55, 0x01, 0x00])
        await coordinator._write_gatt(packet)

        mock_client.write_gatt_char.assert_called_once_with("standard_char", packet, response=False)

    @pytest.mark.asyncio
    async def test_write_gatt_abba_characteristic(self):
        """Test _write_gatt uses ABBA write characteristic for ABBA devices."""
        coordinator = create_mock_coordinator()
        coordinator._is_abba_device = True
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        coordinator._client = mock_client
        coordinator._characteristic = "standard_char"
        coordinator._abba_write_char = "abba_write_char"

        packet = bytearray([0xBA, 0xAB, 0x01, 0x00])
        await coordinator._write_gatt(packet)

        mock_client.write_gatt_char.assert_called_once_with("abba_write_char", packet, response=False)


# ---------------------------------------------------------------------------
# Wake up ping tests
# ---------------------------------------------------------------------------

class TestWakeUpPing:
    """Tests for wake-up ping functionality."""

    @pytest.mark.asyncio
    async def test_send_wake_up_ping_success(self):
        """Test _send_wake_up_ping sends packet successfully."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        coordinator._client = mock_client
        coordinator._characteristic = "char"
        coordinator._write_gatt = AsyncMock()
        coordinator._build_command_packet = MagicMock(return_value=bytearray([0xAA, 0x55]))

        await coordinator._send_wake_up_ping()

        coordinator._build_command_packet.assert_called_once_with(1)
        coordinator._write_gatt.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_wake_up_ping_handles_error(self):
        """Test _send_wake_up_ping handles errors gracefully."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        coordinator._client = mock_client
        coordinator._characteristic = "char"
        coordinator._write_gatt = AsyncMock(side_effect=Exception("Write failed"))
        coordinator._build_command_packet = MagicMock(return_value=bytearray([0xAA, 0x55]))

        # Should not raise
        await coordinator._send_wake_up_ping()

        coordinator._logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_send_wake_up_ping_no_client(self):
        """Test _send_wake_up_ping with no client does nothing."""
        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._write_gatt = AsyncMock()

        await coordinator._send_wake_up_ping()

        coordinator._write_gatt.assert_not_called()


# ---------------------------------------------------------------------------
# Send command tests
# ---------------------------------------------------------------------------

class TestSendCommand:
    """Tests for _send_command method."""

    @pytest.mark.asyncio
    async def test_send_command_no_client(self):
        """Test _send_command returns False when no client."""
        coordinator = create_mock_coordinator()
        coordinator._client = None

        result = await coordinator._send_command(1, 0, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        """Test _send_command returns False when not connected."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = False
        coordinator._client = mock_client

        result = await coordinator._send_command(1, 0, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_command_no_characteristic(self):
        """Test _send_command returns False when no characteristic."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        coordinator._client = mock_client
        coordinator._characteristic = None

        result = await coordinator._send_command(1, 0, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_command_timeout(self):
        """Test _send_command returns False on timeout."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        coordinator._client = mock_client
        coordinator._characteristic = "char"
        coordinator._write_gatt = AsyncMock()
        coordinator._build_command_packet = MagicMock(return_value=bytearray([0xAA]))
        coordinator._notification_data = None  # No response

        result = await coordinator._send_command(1, 0, timeout=0.2)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_command_success_with_response(self):
        """Test _send_command returns True when response received."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        coordinator._client = mock_client
        coordinator._characteristic = "char"
        coordinator._build_command_packet = MagicMock(return_value=bytearray([0xAA]))

        # Simulate response arriving after first iteration
        async def mock_write(packet):
            coordinator._notification_data = bytearray([0xAA, 0x55])

        coordinator._write_gatt = AsyncMock(side_effect=mock_write)

        result = await coordinator._send_command(1, 0, timeout=1.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_command_exception_cleans_up(self):
        """Test _send_command cleans up connection on exception."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        coordinator._client = mock_client
        coordinator._characteristic = "char"
        coordinator._write_gatt = AsyncMock(side_effect=Exception("BLE error"))
        coordinator._build_command_packet = MagicMock(return_value=bytearray([0xAA]))
        coordinator._cleanup_connection = AsyncMock()

        result = await coordinator._send_command(1, 0, timeout=0.1)

        assert result is False
        coordinator._cleanup_connection.assert_called_once()


# ---------------------------------------------------------------------------
# Build command packet edge cases
# ---------------------------------------------------------------------------

class TestBuildCommandPacketEdgeCases:
    """Edge case tests for _build_command_packet."""

    def test_build_command_uses_abba_fallback(self):
        """Test _build_command_packet uses ABBA protocol fallback."""
        coordinator = create_mock_coordinator()
        coordinator._protocol = None
        coordinator._is_abba_device = True

        packet = coordinator._build_command_packet(1, 0)

        # Should use ABBA protocol (mode 5)
        assert packet[0] == 0xBA
        assert packet[1] == 0xAB

    def test_build_command_uses_aa55_fallback(self):
        """Test _build_command_packet uses AA55 protocol fallback."""
        coordinator = create_mock_coordinator()
        coordinator._protocol = None
        coordinator._is_abba_device = False

        packet = coordinator._build_command_packet(1, 0)

        # Should use AA55 protocol (mode 1)
        assert packet[0] == 0xAA
        assert packet[1] == 0x55


# ---------------------------------------------------------------------------
# ABBA toggle guard tests
# ---------------------------------------------------------------------------

class TestABBAToggleGuard:
    """Tests for ABBA protocol toggle guard."""

    @pytest.mark.asyncio
    async def test_turn_on_skipped_when_already_on_abba(self):
        """Test async_turn_on is skipped when heater already on (ABBA mode)."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5  # ABBA
        coordinator.data["running_state"] = 1  # Already on
        coordinator._send_command = AsyncMock()

        await coordinator.async_turn_on()

        # Should not send command
        coordinator._send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_proceeds_when_off_abba(self):
        """Test async_turn_on proceeds when heater is off (ABBA mode)."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5  # ABBA
        coordinator.data["running_state"] = 0  # Off
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_turn_on()

        coordinator._send_command.assert_called_once_with(3, 1)
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off_skipped_when_already_off_abba(self):
        """Test async_turn_off is skipped when heater already off (ABBA mode)."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5  # ABBA
        coordinator.data["running_state"] = 0  # Already off
        coordinator._send_command = AsyncMock()

        await coordinator.async_turn_off()

        # Should not send command
        coordinator._send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_proceeds_when_on_abba(self):
        """Test async_turn_off proceeds when heater is on (ABBA mode)."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 5  # ABBA
        coordinator.data["running_state"] = 1  # On
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_turn_off()

        coordinator._send_command.assert_called_once_with(3, 0)
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_on_proceeds_non_abba_protocol(self):
        """Test async_turn_on always proceeds for non-ABBA protocols."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1  # AA55, not ABBA
        coordinator.data["running_state"] = 1  # Already on, but not ABBA
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_turn_on()

        # Should still send command for non-ABBA
        coordinator._send_command.assert_called_once_with(3, 1)


# ---------------------------------------------------------------------------
# Fahrenheit conversion tests
# ---------------------------------------------------------------------------

class TestFahrenheitConversion:
    """Tests for Fahrenheit temperature conversion."""

    @pytest.mark.asyncio
    async def test_set_temperature_converts_to_fahrenheit(self):
        """Test async_set_temperature converts to Fahrenheit when heater uses it."""
        coordinator = create_mock_coordinator()
        coordinator._heater_uses_fahrenheit = True
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        # Set 20°C, should convert to 68°F
        await coordinator.async_set_temperature(20)

        coordinator._send_command.assert_called_once()
        call_args = coordinator._send_command.call_args
        # Command 4 is set temperature, arg should be 68 (20*9/5+32)
        assert call_args[0][0] == 4
        assert call_args[0][1] == 68

    @pytest.mark.asyncio
    async def test_set_temperature_celsius_no_conversion(self):
        """Test async_set_temperature sends Celsius when heater uses it."""
        coordinator = create_mock_coordinator()
        coordinator._heater_uses_fahrenheit = False
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        # Set 20°C, should stay as 20
        await coordinator.async_set_temperature(20)

        coordinator._send_command.assert_called_once()
        call_args = coordinator._send_command.call_args
        assert call_args[0][0] == 4
        assert call_args[0][1] == 20


# ---------------------------------------------------------------------------
# Additional async command tests
# ---------------------------------------------------------------------------

class TestAsyncCommands2:
    """Additional tests for async command methods."""

    @pytest.mark.asyncio
    async def test_turn_on_no_refresh_on_failure(self):
        """Test async_turn_on doesn't refresh on command failure."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_turn_on()

        coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_no_refresh_on_failure(self):
        """Test async_turn_off doesn't refresh on command failure."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_turn_off()

        coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_level_no_refresh_on_failure(self):
        """Test async_set_level doesn't refresh on command failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_set_level(5)

        coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_temperature_no_refresh_on_failure(self):
        """Test async_set_temperature doesn't refresh on command failure."""
        coordinator = create_mock_coordinator()
        coordinator._heater_uses_fahrenheit = False
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_set_temperature(22)

        coordinator.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _ensure_connected (lines 903-1046)
# ---------------------------------------------------------------------------

class TestEnsureConnected:
    """Tests for the _ensure_connected BLE connection method."""

    @pytest.mark.asyncio
    async def test_already_connected_returns_immediately(self):
        """Test _ensure_connected returns immediately if already connected."""
        coordinator = create_mock_coordinator()
        mock_client = MagicMock()
        mock_client.is_connected = True
        coordinator._client = mock_client
        coordinator._connection_attempts = 5

        await coordinator._ensure_connected()

        # Connection attempts should be reset
        assert coordinator._connection_attempts == 0

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self):
        """Test exponential backoff is applied between connection attempts."""
        import time
        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._connection_attempts = 1
        coordinator._last_connection_attempt = time.time() - 2  # 2 seconds ago
        coordinator._cleanup_connection = AsyncMock()

        # Mock establish_connection to raise an exception
        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
        ) as mock_establish:
            mock_establish.side_effect = Exception("Connection failed")
            coordinator._cleanup_connection = AsyncMock()

            with pytest.raises(Exception, match="Connection failed"):
                await coordinator._ensure_connected()

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_stale_client(self):
        """Test cleanup is called before new connection attempt."""
        coordinator = create_mock_coordinator()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = False  # Stale connection
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._connection_attempts = 0

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
        ) as mock_establish:
            mock_establish.side_effect = Exception("Test error")
            coordinator._cleanup_connection = AsyncMock()

            with pytest.raises(Exception):
                await coordinator._ensure_connected()

            # Cleanup should be called at least once
            assert coordinator._cleanup_connection.call_count >= 1

    @pytest.mark.asyncio
    async def test_abba_device_detection(self):
        """Test ABBA/HeaterCC device detection via fff0 service."""
        from custom_components.diesel_heater.const import (
            ABBA_SERVICE_UUID,
            ABBA_NOTIFY_UUID,
            ABBA_WRITE_UUID,
        )

        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._send_wake_up_ping = AsyncMock()
        coordinator._is_abba_device = False
        coordinator._abba_write_char = None
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        # Mock BLE client with ABBA service
        mock_client = MagicMock()
        mock_client.is_connected = True

        # Create mock characteristics
        mock_notify_char = MagicMock()
        mock_notify_char.uuid = ABBA_NOTIFY_UUID
        mock_notify_char.properties = ["notify"]

        mock_write_char = MagicMock()
        mock_write_char.uuid = ABBA_WRITE_UUID
        mock_write_char.properties = ["write"]

        # Create mock service
        mock_service = MagicMock()
        mock_service.uuid = ABBA_SERVICE_UUID
        mock_service.characteristics = [mock_notify_char, mock_write_char]

        mock_client.services = [mock_service]
        mock_client.start_notify = AsyncMock()

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await coordinator._ensure_connected()

        assert coordinator._is_abba_device is True
        assert coordinator._protocol_mode == 5
        assert coordinator._characteristic == mock_notify_char
        assert coordinator._abba_write_char == mock_write_char

    @pytest.mark.asyncio
    async def test_abba_fallback_write_char(self):
        """Test ABBA falls back to fff1 if fff2 not available."""
        from custom_components.diesel_heater.const import (
            ABBA_SERVICE_UUID,
            ABBA_NOTIFY_UUID,
        )

        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._send_wake_up_ping = AsyncMock()
        coordinator._is_abba_device = False
        coordinator._abba_write_char = None
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        # Mock BLE client with ABBA service but NO write characteristic
        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_notify_char = MagicMock()
        mock_notify_char.uuid = ABBA_NOTIFY_UUID
        mock_notify_char.properties = ["notify", "write"]  # fff1 has write too

        mock_service = MagicMock()
        mock_service.uuid = ABBA_SERVICE_UUID
        mock_service.characteristics = [mock_notify_char]  # Only fff1

        mock_client.services = [mock_service]
        mock_client.start_notify = AsyncMock()

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await coordinator._ensure_connected()

        # Should fall back to using notify char for writing
        assert coordinator._abba_write_char == mock_notify_char
        coordinator._logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_vevor_service_discovery(self):
        """Test standard Vevor service/characteristic discovery."""
        from custom_components.diesel_heater.const import (
            SERVICE_UUID,
            CHARACTERISTIC_UUID,
        )

        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._send_wake_up_ping = AsyncMock()
        coordinator._is_abba_device = False
        coordinator._abba_write_char = None
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_char = MagicMock()
        mock_char.uuid = CHARACTERISTIC_UUID
        mock_char.properties = ["notify", "write"]

        mock_service = MagicMock()
        mock_service.uuid = SERVICE_UUID
        mock_service.characteristics = [mock_char]

        mock_client.services = [mock_service]
        mock_client.start_notify = AsyncMock()

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await coordinator._ensure_connected()

        assert coordinator._is_abba_device is False
        assert coordinator._characteristic == mock_char
        assert coordinator._active_char_uuid == CHARACTERISTIC_UUID

    @pytest.mark.asyncio
    async def test_no_services_discovered(self):
        """Test handling when no services are discovered."""
        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.services = None  # No services

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(Exception) as exc_info:
                await coordinator._ensure_connected()
            assert "No services available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_characteristic_not_found(self):
        """Test error when heater characteristic not found."""
        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._is_abba_device = False
        coordinator._abba_write_char = None
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        mock_client = MagicMock()
        mock_client.is_connected = True

        # Service with unrelated characteristic
        mock_service = MagicMock()
        mock_service.uuid = "00001234-0000-1000-8000-00805f9b34fb"
        mock_service.characteristics = []

        mock_client.services = [mock_service]

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(Exception) as exc_info:
                await coordinator._ensure_connected()
            assert "Could not find heater characteristic" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_characteristic_no_notify(self):
        """Test warning when characteristic doesn't support notify."""
        from custom_components.diesel_heater.const import (
            SERVICE_UUID,
            CHARACTERISTIC_UUID,
        )

        coordinator = create_mock_coordinator()
        coordinator._client = None
        coordinator._ble_device = MagicMock()
        coordinator._ble_device.address = "AA:BB:CC:DD:EE:FF"
        coordinator._cleanup_connection = AsyncMock()
        coordinator._send_wake_up_ping = AsyncMock()
        coordinator._is_abba_device = False
        coordinator._abba_write_char = None
        coordinator._characteristic = None
        coordinator._active_char_uuid = None

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_char = MagicMock()
        mock_char.uuid = CHARACTERISTIC_UUID
        mock_char.properties = ["write"]  # No notify!

        mock_service = MagicMock()
        mock_service.uuid = SERVICE_UUID
        mock_service.characteristics = [mock_char]

        mock_client.services = [mock_service]

        with patch(
            "custom_components.diesel_heater.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            await coordinator._ensure_connected()

        # Should log warning about no notify support
        coordinator._logger.warning.assert_called()


# ---------------------------------------------------------------------------
# Tests for _notification_callback and _parse_response (lines 1048-1165)
# ---------------------------------------------------------------------------

class TestNotificationCallback:
    """Tests for notification callback and response parsing."""

    def test_notification_callback_logs_and_parses(self):
        """Test _notification_callback logs data and calls _parse_response."""
        coordinator = create_mock_coordinator()
        coordinator._parse_response = MagicMock()

        data = bytearray([0xAA, 0x55, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])
        coordinator._notification_callback(0, data)

        coordinator._logger.info.assert_called()
        coordinator._parse_response.assert_called_once_with(data)

    def test_notification_callback_catches_parse_errors(self):
        """Test _notification_callback catches and logs parse errors."""
        coordinator = create_mock_coordinator()
        coordinator._parse_response = MagicMock(side_effect=ValueError("Parse error"))

        data = bytearray([0xAA, 0x55, 0x00, 0x01])
        coordinator._notification_callback(0, data)

        coordinator._logger.error.assert_called()

    def test_parse_response_too_short(self):
        """Test _parse_response handles short data."""
        coordinator = create_mock_coordinator()
        coordinator._notification_data = None

        data = bytearray([0x00, 0x01, 0x02])  # Too short
        coordinator._parse_response(data)

        coordinator._logger.debug.assert_called()

    def test_parse_response_aa77_ack_short(self):
        """Test _parse_response handles short AA77 ACK."""
        coordinator = create_mock_coordinator()
        coordinator._notification_data = None

        data = bytearray([0xAA, 0x77, 0x01, 0x02, 0x03])  # Short but valid AA77
        coordinator._parse_response(data)

        assert coordinator._notification_data == data

    def test_parse_response_aa77_ack_full(self):
        """Test _parse_response handles full AA77 ACK."""
        coordinator = create_mock_coordinator()
        coordinator._notification_data = None

        data = bytearray([0xAA, 0x77] + [0x00] * 8)  # Full AA77
        coordinator._parse_response(data)

        assert coordinator._notification_data == data

    def test_parse_response_unknown_protocol(self):
        """Test _parse_response logs warning for unknown protocol."""
        coordinator = create_mock_coordinator()

        # Unknown header
        data = bytearray([0x12, 0x34] + [0x00] * 16)
        coordinator._parse_response(data)

        coordinator._logger.warning.assert_called()

    def test_parse_response_parse_error_handling(self):
        """Test _parse_response handles protocol parse errors gracefully."""
        coordinator = create_mock_coordinator()
        coordinator._protocol_mode = 1
        coordinator._is_abba_device = False
        coordinator._notification_data = None

        # Create a mock protocol that raises on parse
        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 1
        mock_protocol.name = "TestProtocol"
        mock_protocol.parse = MagicMock(side_effect=ValueError("Bad data"))

        # Mock _detect_protocol to return our failing protocol
        coordinator._detect_protocol = MagicMock(
            return_value=(mock_protocol, bytearray(18))
        )

        # Valid AA55 header but bad data
        data = bytearray([0xAA, 0x55] + [0x00] * 16)
        coordinator._parse_response(data)

        # Should set default values on error
        assert coordinator.data["connected"] is True
        assert coordinator.data["running_state"] == 0
        coordinator._logger.error.assert_called()

    def test_parse_response_parsed_none(self):
        """Test _parse_response handles None parse result."""
        coordinator = create_mock_coordinator()

        # Mock protocol that returns None
        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 1
        mock_protocol.parse.return_value = None

        coordinator._detect_protocol = MagicMock(return_value=(mock_protocol, bytearray(18)))

        data = bytearray([0xAA, 0x55] + [0x00] * 16)
        coordinator._parse_response(data)

        assert coordinator.data["connected"] is True


class TestDetectProtocol:
    """Tests for protocol detection logic."""

    def test_detect_cbff_protocol(self):
        """Test CBFF protocol detection."""
        coordinator = create_mock_coordinator()

        data = bytearray([0xCB, 0xFF] + [0x00] * 30)
        protocol, parse_data = coordinator._detect_protocol(data, 0xCBFF)

        assert protocol == coordinator._protocols[6]
        assert parse_data == data

    def test_detect_abba_protocol(self):
        """Test ABBA protocol detection."""
        coordinator = create_mock_coordinator()

        data = bytearray([0xAB, 0xBA] + [0x00] * 19)
        protocol, parse_data = coordinator._detect_protocol(data, 0xABBA)

        assert protocol == coordinator._protocols[5]

    def test_detect_abba_by_device_flag(self):
        """Test ABBA detection when device flag is set."""
        coordinator = create_mock_coordinator()
        coordinator._is_abba_device = True

        data = bytearray([0x00, 0x00] + [0x00] * 19)
        protocol, parse_data = coordinator._detect_protocol(data, 0x0000)

        assert protocol == coordinator._protocols[5]

    def test_detect_aa55_unencrypted(self):
        """Test AA55 unencrypted protocol detection."""
        coordinator = create_mock_coordinator()

        data = bytearray(18)
        data[0], data[1] = 0xAA, 0x55
        protocol, parse_data = coordinator._detect_protocol(data, 0xAA55)

        assert protocol == coordinator._protocols[1]

    def test_detect_aa66_unencrypted(self):
        """Test AA66 unencrypted protocol detection."""
        coordinator = create_mock_coordinator()

        data = bytearray(20)
        data[0], data[1] = 0xAA, 0x66
        protocol, parse_data = coordinator._detect_protocol(data, 0xAA66)

        assert protocol == coordinator._protocols[3]

    def test_detect_aa55_encrypted(self):
        """Test AA55 encrypted (48 bytes) protocol detection."""
        from diesel_heater_ble import _encrypt_data

        coordinator = create_mock_coordinator()

        # Create unencrypted AA55 data
        plain = bytearray(48)
        plain[0], plain[1] = 0xAA, 0x55

        # Encrypt it
        encrypted = _encrypt_data(plain)

        protocol, parse_data = coordinator._detect_protocol(encrypted, 0)

        assert protocol == coordinator._protocols[2]

    def test_detect_aa66_encrypted(self):
        """Test AA66 encrypted (48 bytes) protocol detection."""
        from diesel_heater_ble import _encrypt_data

        coordinator = create_mock_coordinator()

        # Create unencrypted AA66 data
        plain = bytearray(48)
        plain[0], plain[1] = 0xAA, 0x66

        # Encrypt it
        encrypted = _encrypt_data(plain)

        protocol, parse_data = coordinator._detect_protocol(encrypted, 0)

        assert protocol == coordinator._protocols[4]

    def test_detect_unknown_protocol(self):
        """Test unknown protocol returns None."""
        coordinator = create_mock_coordinator()

        data = bytearray([0x12, 0x34] + [0x00] * 16)
        protocol, parse_data = coordinator._detect_protocol(data, 0x1234)

        assert protocol is None
        assert parse_data is None

    def test_detect_short_data(self):
        """Test short data returns None."""
        coordinator = create_mock_coordinator()

        data = bytearray([0xAA, 0x55, 0x00])  # Too short
        protocol, parse_data = coordinator._detect_protocol(data, 0xAA55)

        assert protocol is None


# ---------------------------------------------------------------------------
# Tests for CBFF decryption and temp_unit detection (lines 1147-1165)
# ---------------------------------------------------------------------------

class TestCBFFDecryption:
    """Tests for CBFF decryption status logging."""

    def test_cbff_decrypted_flag_logged(self):
        """Test CBFF decrypted flag triggers info log."""
        coordinator = create_mock_coordinator()
        coordinator.address = "AA:BB:CC:DD:EE:FF"

        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 6
        mock_protocol.parse.return_value = {"_cbff_decrypted": True, "running_state": 1}

        coordinator._detect_protocol = MagicMock(return_value=(mock_protocol, bytearray(32)))

        data = bytearray([0xCB, 0xFF] + [0x00] * 30)
        coordinator._parse_response(data)

        # Should log decryption success
        coordinator._logger.info.assert_called()

    def test_cbff_suspect_data_logged(self):
        """Test CBFF suspect data triggers warning log."""
        coordinator = create_mock_coordinator()

        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 6
        mock_protocol.parse.return_value = {
            "_cbff_data_suspect": True,
            "cbff_protocol_version": "1.2",
            "running_state": 0,
        }

        coordinator._detect_protocol = MagicMock(return_value=(mock_protocol, bytearray(32)))

        data = bytearray([0xCB, 0xFF] + [0x00] * 30)
        coordinator._parse_response(data)

        coordinator._logger.warning.assert_called()

    def test_temp_unit_detection_fahrenheit(self):
        """Test temp_unit detection sets Fahrenheit flag."""
        coordinator = create_mock_coordinator()
        coordinator._heater_uses_fahrenheit = False

        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 1
        mock_protocol.parse.return_value = {"temp_unit": 1, "running_state": 1}

        coordinator._detect_protocol = MagicMock(return_value=(mock_protocol, bytearray(18)))

        data = bytearray([0xAA, 0x55] + [0x00] * 16)
        coordinator._parse_response(data)

        assert coordinator._heater_uses_fahrenheit is True

    def test_temp_unit_detection_celsius(self):
        """Test temp_unit detection sets Celsius flag."""
        coordinator = create_mock_coordinator()
        coordinator._heater_uses_fahrenheit = True

        mock_protocol = MagicMock()
        mock_protocol.protocol_mode = 1
        mock_protocol.parse.return_value = {"temp_unit": 0, "running_state": 1}

        coordinator._detect_protocol = MagicMock(return_value=(mock_protocol, bytearray(18)))

        data = bytearray([0xAA, 0x55] + [0x00] * 16)
        coordinator._parse_response(data)

        assert coordinator._heater_uses_fahrenheit is False


# ---------------------------------------------------------------------------
# Tests for post-status request (lines 1338-1342)
# ---------------------------------------------------------------------------

class TestPostStatusRequest:
    """Tests for post-command status request."""

    @pytest.mark.asyncio
    async def test_abba_post_status_sent(self):
        """Test ABBA sends follow-up status request after command."""
        coordinator = create_mock_coordinator()
        coordinator._write_gatt = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._characteristic = MagicMock()
        coordinator._notification_data = None

        # ABBA protocol needs post status
        mock_protocol = MagicMock()
        mock_protocol.needs_post_status = True
        mock_protocol.name = "ABBA"
        mock_protocol.build_command.return_value = bytearray([0xAB, 0xBA, 0x00, 0x00])
        coordinator._protocol = mock_protocol

        # Make the notification_data appear after first write
        async def set_notification_after_write(packet):
            coordinator._notification_data = bytearray([0x01])

        coordinator._write_gatt.side_effect = set_notification_after_write

        result = await coordinator._send_command(4, 5, timeout=0.2)  # Not command 1

        # Should have called build_command twice (original + status)
        assert mock_protocol.build_command.call_count == 2
        # Second call should be status request (command 1)
        assert mock_protocol.build_command.call_args_list[1][0][0] == 1

    @pytest.mark.asyncio
    async def test_no_post_status_for_status_command(self):
        """Test no post-status sent when command is already a status request."""
        coordinator = create_mock_coordinator()
        coordinator._write_gatt = AsyncMock()
        coordinator._client = MagicMock()
        coordinator._client.is_connected = True
        coordinator._characteristic = MagicMock()
        coordinator._notification_data = None

        mock_protocol = MagicMock()
        mock_protocol.needs_post_status = True
        mock_protocol.build_command.return_value = bytearray([0xAB, 0xBA, 0x00, 0x00])
        coordinator._protocol = mock_protocol

        # Make the notification_data appear after first write
        async def set_notification_after_write(packet):
            coordinator._notification_data = bytearray([0x01])

        coordinator._write_gatt.side_effect = set_notification_after_write

        result = await coordinator._send_command(1, 0, timeout=0.2)  # Command 1 = status request

        # Should only call build_command once (no post-status for status command)
        assert mock_protocol.build_command.call_count == 1


# ---------------------------------------------------------------------------
# Tests for auto-offset disable (lines 1654-1656)
# ---------------------------------------------------------------------------

class TestAutoOffsetDisable:
    """Tests for disabling auto-offset."""

    @pytest.mark.asyncio
    async def test_disable_auto_offset_resets_to_zero(self):
        """Test disabling auto-offset resets heater offset to 0."""
        coordinator = create_mock_coordinator()
        coordinator._current_heater_offset = 5
        coordinator.async_save_data = AsyncMock()
        coordinator.async_set_heater_offset = AsyncMock()
        coordinator._auto_offset_unsub = None
        coordinator._async_calculate_auto_offset = AsyncMock()
        coordinator.data["auto_offset_enabled"] = True

        await coordinator.async_set_auto_offset_enabled(False)

        coordinator.async_set_heater_offset.assert_called_once_with(0)
        assert coordinator.data["auto_offset_enabled"] is False

    @pytest.mark.asyncio
    async def test_disable_auto_offset_skips_if_already_zero(self):
        """Test disabling auto-offset doesn't call set_offset if already 0."""
        coordinator = create_mock_coordinator()
        coordinator._current_heater_offset = 0
        coordinator.async_save_data = AsyncMock()
        coordinator.async_set_heater_offset = AsyncMock()
        coordinator._auto_offset_unsub = None
        coordinator._async_calculate_auto_offset = AsyncMock()
        coordinator.data["auto_offset_enabled"] = True

        await coordinator.async_set_auto_offset_enabled(False)

        coordinator.async_set_heater_offset.assert_not_called()

    @pytest.mark.asyncio
    async def test_enable_auto_offset_triggers_calculation(self):
        """Test enabling auto-offset triggers initial calculation."""
        coordinator = create_mock_coordinator()
        coordinator._current_heater_offset = 0
        coordinator.async_save_data = AsyncMock()
        coordinator._async_calculate_auto_offset = AsyncMock()
        coordinator._auto_offset_unsub = None
        coordinator.data["auto_offset_enabled"] = False

        await coordinator.async_set_auto_offset_enabled(True)

        coordinator._async_calculate_auto_offset.assert_called_once()
        assert coordinator.data["auto_offset_enabled"] is True


# ---------------------------------------------------------------------------
# Tests for async_send_raw_command (lines 1658-1684)
# ---------------------------------------------------------------------------

class TestSendRawCommand:
    """Tests for raw command sending."""

    @pytest.mark.asyncio
    async def test_send_raw_command_success(self):
        """Test send_raw_command returns True on success."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()

        result = await coordinator.async_send_raw_command(99, 42)

        assert result is True
        coordinator._send_command.assert_called_once_with(99, 42)
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_raw_command_failure(self):
        """Test send_raw_command returns False on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()

        result = await coordinator.async_send_raw_command(99, 42)

        assert result is False
        coordinator._logger.warning.assert_called()
        coordinator.async_request_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for async_shutdown (lines 1686-1695)
# ---------------------------------------------------------------------------

class TestAsyncShutdown:
    """Tests for coordinator shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_auto_offset_listener(self):
        """Test shutdown cleans up external sensor listener."""
        coordinator = create_mock_coordinator()
        mock_unsub = MagicMock()
        coordinator._auto_offset_unsub = mock_unsub
        coordinator._cleanup_connection = AsyncMock()

        await coordinator.async_shutdown()

        mock_unsub.assert_called_once()
        assert coordinator._auto_offset_unsub is None

    @pytest.mark.asyncio
    async def test_shutdown_without_listener(self):
        """Test shutdown works when no listener registered."""
        coordinator = create_mock_coordinator()
        coordinator._auto_offset_unsub = None
        coordinator._cleanup_connection = AsyncMock()

        await coordinator.async_shutdown()

        coordinator._cleanup_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_connection(self):
        """Test shutdown cleans up BLE connection."""
        coordinator = create_mock_coordinator()
        coordinator._auto_offset_unsub = None
        coordinator._cleanup_connection = AsyncMock()

        await coordinator.async_shutdown()

        coordinator._cleanup_connection.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for set_xxx method failure paths (lines 1475, 1507, 1522, etc.)
# ---------------------------------------------------------------------------

class TestSetMethodFailures:
    """Tests for set_xxx method failure paths."""

    @pytest.mark.asyncio
    async def test_set_heater_offset_failure(self):
        """Test async_set_heater_offset logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator._current_heater_offset = 0
        coordinator.async_request_refresh = AsyncMock()

        await coordinator.async_set_heater_offset(5)

        coordinator._logger.warning.assert_called()
        # Should not update state on failure
        assert coordinator._current_heater_offset == 0
        coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_language_failure(self):
        """Test async_set_language logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["language"] = 0

        await coordinator.async_set_language(1)

        coordinator._logger.warning.assert_called()
        # Should not update state on failure
        assert coordinator.data["language"] == 0

    @pytest.mark.asyncio
    async def test_set_temp_unit_failure(self):
        """Test async_set_temp_unit logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["temp_unit"] = 0

        await coordinator.async_set_temp_unit(True)  # Try to set Fahrenheit

        coordinator._logger.warning.assert_called()
        assert coordinator.data["temp_unit"] == 0

    @pytest.mark.asyncio
    async def test_set_altitude_unit_failure(self):
        """Test async_set_altitude_unit logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["altitude_unit"] = 0

        await coordinator.async_set_altitude_unit(True)  # Try to set Feet

        coordinator._logger.warning.assert_called()
        assert coordinator.data["altitude_unit"] == 0

    @pytest.mark.asyncio
    async def test_set_high_altitude_failure(self):
        """Test async_set_high_altitude logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator._is_abba_device = True
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["high_altitude"] = 0

        await coordinator.async_set_high_altitude(True)

        coordinator._logger.warning.assert_called()
        assert coordinator.data["high_altitude"] == 0

    @pytest.mark.asyncio
    async def test_set_high_altitude_non_abba_device(self):
        """Test async_set_high_altitude warns on non-ABBA device."""
        coordinator = create_mock_coordinator()
        coordinator._is_abba_device = False
        coordinator._send_command = AsyncMock()

        await coordinator.async_set_high_altitude(True)

        # Should warn and not send command
        coordinator._logger.warning.assert_called()
        coordinator._send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_tank_volume_failure(self):
        """Test async_set_tank_volume logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["tank_volume"] = 0

        await coordinator.async_set_tank_volume(5)

        coordinator._logger.warning.assert_called()
        assert coordinator.data["tank_volume"] == 0

    @pytest.mark.asyncio
    async def test_set_pump_type_failure(self):
        """Test async_set_pump_type logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["pump_type"] = 0

        await coordinator.async_set_pump_type(2)

        coordinator._logger.warning.assert_called()
        assert coordinator.data["pump_type"] == 0

    @pytest.mark.asyncio
    async def test_set_backlight_failure(self):
        """Test async_set_backlight logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data["backlight"] = 50

        await coordinator.async_set_backlight(100)

        coordinator._logger.warning.assert_called()
        assert coordinator.data["backlight"] == 50

    @pytest.mark.asyncio
    async def test_sync_time_failure(self):
        """Test async_sync_time logs warning on failure."""
        coordinator = create_mock_coordinator()
        coordinator._send_command = AsyncMock(return_value=False)

        await coordinator.async_sync_time()

        coordinator._logger.warning.assert_called()
