"""Tests for Diesel Heater switch platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.switch import (
    VevorHeaterPowerSwitch,
    VevorAutoStartStopSwitch,
    VevorAutoOffsetSwitch,
    VevorTempUnitSwitch,
    VevorAltitudeUnitSwitch,
    VevorHighAltitudeSwitch,
    async_setup_entry,
)


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for switch testing."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_turn_on = AsyncMock()
    coordinator.async_turn_off = AsyncMock()
    coordinator.async_set_auto_start_stop = AsyncMock()
    coordinator.async_set_auto_offset_enabled = AsyncMock()
    coordinator.async_set_temp_unit = AsyncMock()
    coordinator.async_set_altitude_unit = AsyncMock()
    coordinator.async_set_high_altitude = AsyncMock()
    coordinator._is_abba_device = False
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"external_temp_sensor": "sensor.test"}
    coordinator.data = {
        "connected": True,
        "running_state": 1,
        "running_step": 3,
        "running_mode": 2,  # Temperature mode
        "set_level": 5,
        "set_temp": 22,
        "auto_start_stop": 1,
        "auto_offset_enabled": False,
        "temp_unit": 0,  # Celsius
        "altitude_unit": 0,  # Meters
        "high_altitude": 0,  # Disabled
    }
    return coordinator


# ---------------------------------------------------------------------------
# Power switch tests
# ---------------------------------------------------------------------------

class TestVevorHeaterPowerSwitch:
    """Tests for Vevor power switch entity."""

    def test_is_on_when_running(self):
        """Test is_on returns True when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 1
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch.is_on is True

    def test_is_on_when_off(self):
        """Test is_on returns False when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 0
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch.is_on is False

    def test_is_on_when_none(self):
        """Test is_on returns False when running_state is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = None
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch.is_on is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        assert "_power" in switch.unique_id

    def test_has_entity_name(self):
        """Test has_entity_name is True."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch._attr_has_entity_name is True

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch._attr_name == "Power"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch._attr_icon == "mdi:power"

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch._attr_device_info is not None
        assert "identifiers" in switch._attr_device_info

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on calls coordinator."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_turn_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off calls coordinator."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_turn_off.assert_called_once()


# ---------------------------------------------------------------------------
# Auto start/stop switch tests
# ---------------------------------------------------------------------------

class TestVevorAutoStartStopSwitch:
    """Tests for Vevor auto start/stop switch entity."""

    def test_is_on_when_enabled(self):
        """Test is_on returns truthy when auto start/stop is enabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_start_stop"] = 1
        switch = VevorAutoStartStopSwitch(coordinator)

        # Returns 1 which is truthy
        assert switch.is_on

    def test_is_on_when_disabled(self):
        """Test is_on returns falsy when auto start/stop is disabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_start_stop"] = 0
        switch = VevorAutoStartStopSwitch(coordinator)

        # Returns 0 which is falsy
        assert not switch.is_on

    def test_is_on_when_none(self):
        """Test is_on returns None when auto_start_stop is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_start_stop"] = None
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch.is_on is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)

        assert "_auto_start_stop" in switch.unique_id

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch._attr_name == "Auto Start/Stop"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch._attr_icon == "mdi:thermostat-auto"

    def test_available_in_temp_mode(self):
        """Test available when in temperature mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = 2  # Temperature mode
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch.available is True

    def test_unavailable_in_level_mode(self):
        """Test unavailable when in level mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = 1  # Level mode
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch.available is False

    def test_unavailable_when_disconnected(self):
        """Test unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        switch = VevorAutoStartStopSwitch(coordinator)

        assert switch.available is False

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on enables auto start/stop."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_set_auto_start_stop.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off disables auto start/stop."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_set_auto_start_stop.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# Auto offset switch tests
# ---------------------------------------------------------------------------

class TestVevorAutoOffsetSwitch:
    """Tests for Vevor auto offset switch entity."""

    def test_is_on_when_enabled(self):
        """Test is_on returns True when auto offset is enabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = True
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch.is_on is True

    def test_is_on_when_disabled(self):
        """Test is_on returns False when auto offset is disabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["auto_offset_enabled"] = False
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch.is_on is False

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        assert "_auto_offset" in switch.unique_id

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch._attr_name == "Auto Temperature Offset"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch._attr_icon == "mdi:thermometer-auto"

    def test_entity_category_is_set(self):
        """Test entity_category is set."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch._attr_entity_category is not None

    def test_available_with_external_sensor(self):
        """Test available when external sensor is configured."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.config_entry.data = {"external_temp_sensor": "sensor.test"}
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch.available is True

    def test_unavailable_without_external_sensor(self):
        """Test unavailable when external sensor is not configured."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.config_entry.data = {"external_temp_sensor": ""}
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch.available is False

    def test_unavailable_when_disconnected(self):
        """Test unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        switch = VevorAutoOffsetSwitch(coordinator)

        assert switch.available is False

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on enables auto offset."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_set_auto_offset_enabled.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off disables auto offset."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_set_auto_offset_enabled.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# Temperature unit switch tests
# ---------------------------------------------------------------------------

class TestVevorTempUnitSwitch:
    """Tests for Vevor temperature unit switch entity."""

    def test_is_on_when_fahrenheit(self):
        """Test is_on returns True when using Fahrenheit."""
        coordinator = create_mock_coordinator()
        coordinator.data["temp_unit"] = 1  # Fahrenheit
        switch = VevorTempUnitSwitch(coordinator)

        assert switch.is_on is True

    def test_is_on_when_celsius(self):
        """Test is_on returns False when using Celsius."""
        coordinator = create_mock_coordinator()
        coordinator.data["temp_unit"] = 0  # Celsius
        switch = VevorTempUnitSwitch(coordinator)

        assert switch.is_on is False

    def test_is_on_when_none(self):
        """Test is_on returns None when temp_unit is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["temp_unit"] = None
        switch = VevorTempUnitSwitch(coordinator)

        assert switch.is_on is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        assert "_temp_unit" in switch.unique_id

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        assert switch._attr_name == "Fahrenheit Mode"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        assert switch._attr_icon == "mdi:temperature-fahrenheit"

    def test_entity_category_is_set(self):
        """Test entity_category is set."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        assert switch._attr_entity_category is not None

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on sets Fahrenheit."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_set_temp_unit.assert_called_once_with(use_fahrenheit=True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off sets Celsius."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_set_temp_unit.assert_called_once_with(use_fahrenheit=False)


# ---------------------------------------------------------------------------
# Altitude unit switch tests
# ---------------------------------------------------------------------------

class TestVevorAltitudeUnitSwitch:
    """Tests for Vevor altitude unit switch entity."""

    def test_is_on_when_feet(self):
        """Test is_on returns True when using Feet."""
        coordinator = create_mock_coordinator()
        coordinator.data["altitude_unit"] = 1  # Feet
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch.is_on is True

    def test_is_on_when_meters(self):
        """Test is_on returns False when using Meters."""
        coordinator = create_mock_coordinator()
        coordinator.data["altitude_unit"] = 0  # Meters
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch.is_on is False

    def test_is_on_when_none(self):
        """Test is_on returns None when altitude_unit is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["altitude_unit"] = None
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch.is_on is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert "_altitude_unit" in switch.unique_id

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch._attr_name == "Feet Mode"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch._attr_icon == "mdi:altimeter"

    def test_entity_category_is_set(self):
        """Test entity_category is set."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        assert switch._attr_entity_category is not None

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on sets Feet."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_set_altitude_unit.assert_called_once_with(use_feet=True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off sets Meters."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_set_altitude_unit.assert_called_once_with(use_feet=False)


# ---------------------------------------------------------------------------
# High altitude switch tests
# ---------------------------------------------------------------------------

class TestVevorHighAltitudeSwitch:
    """Tests for Vevor high altitude switch entity."""

    def test_is_on_when_enabled(self):
        """Test is_on returns True when high altitude is enabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["high_altitude"] = 1
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.is_on is True

    def test_is_on_when_disabled(self):
        """Test is_on returns False when high altitude is disabled."""
        coordinator = create_mock_coordinator()
        coordinator.data["high_altitude"] = 0
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.is_on is False

    def test_is_on_when_none(self):
        """Test is_on returns None when high_altitude is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["high_altitude"] = None
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.is_on is None

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        assert "_high_altitude" in switch.unique_id

    def test_name(self):
        """Test name attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch._attr_name == "High Altitude Mode"

    def test_icon(self):
        """Test icon attribute."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch._attr_icon == "mdi:image-filter-hdr"

    def test_entity_category_is_set(self):
        """Test entity_category is set."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch._attr_entity_category is not None

    def test_available_for_abba_device(self):
        """Test available when device is ABBA."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator._is_abba_device = True
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.available is True

    def test_unavailable_for_non_abba_device(self):
        """Test unavailable when device is not ABBA."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator._is_abba_device = False
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.available is False

    def test_unavailable_when_disconnected(self):
        """Test unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        coordinator._is_abba_device = True
        switch = VevorHighAltitudeSwitch(coordinator)

        assert switch.available is False

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on enables high altitude."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        await switch.async_turn_on()

        coordinator.async_set_high_altitude.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off disables high altitude."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)

        await switch.async_turn_off()

        coordinator.async_set_high_altitude.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# Availability tests
# ---------------------------------------------------------------------------

class TestSwitchAvailability:
    """Tests for switch availability."""

    def test_power_available_when_connected(self):
        """Test power switch is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        switch = VevorHeaterPowerSwitch(coordinator)

        assert switch.available is True

    def test_power_available_property_exists(self):
        """Test available property is accessible."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)

        # Just verify property is accessible
        _ = switch.available


# ---------------------------------------------------------------------------
# Entity attributes tests
# ---------------------------------------------------------------------------

class TestSwitchEntityAttributes:
    """Tests for switch entity attributes."""

    def test_all_switches_have_device_info(self):
        """Test all switches have device_info set."""
        coordinator = create_mock_coordinator()

        switches = [
            VevorHeaterPowerSwitch(coordinator),
            VevorAutoStartStopSwitch(coordinator),
            VevorAutoOffsetSwitch(coordinator),
            VevorTempUnitSwitch(coordinator),
            VevorAltitudeUnitSwitch(coordinator),
            VevorHighAltitudeSwitch(coordinator),
        ]

        for switch in switches:
            assert switch._attr_device_info is not None
            assert "identifiers" in switch._attr_device_info

    def test_all_switches_have_unique_id(self):
        """Test all switches have unique_id set."""
        coordinator = create_mock_coordinator()

        switches = [
            VevorHeaterPowerSwitch(coordinator),
            VevorAutoStartStopSwitch(coordinator),
            VevorAutoOffsetSwitch(coordinator),
            VevorTempUnitSwitch(coordinator),
            VevorAltitudeUnitSwitch(coordinator),
            VevorHighAltitudeSwitch(coordinator),
        ]

        unique_ids = set()
        for switch in switches:
            assert switch._attr_unique_id is not None
            unique_ids.add(switch._attr_unique_id)

        # All unique_ids should be different
        assert len(unique_ids) == 6

    def test_all_switches_have_name(self):
        """Test all switches have name set."""
        coordinator = create_mock_coordinator()

        switches = [
            VevorHeaterPowerSwitch(coordinator),
            VevorAutoStartStopSwitch(coordinator),
            VevorAutoOffsetSwitch(coordinator),
            VevorTempUnitSwitch(coordinator),
            VevorAltitudeUnitSwitch(coordinator),
            VevorHighAltitudeSwitch(coordinator),
        ]

        for switch in switches:
            assert switch._attr_name is not None
            assert len(switch._attr_name) > 0

    def test_all_switches_have_icon(self):
        """Test all switches have icon set."""
        coordinator = create_mock_coordinator()

        switches = [
            VevorHeaterPowerSwitch(coordinator),
            VevorAutoStartStopSwitch(coordinator),
            VevorAutoOffsetSwitch(coordinator),
            VevorTempUnitSwitch(coordinator),
            VevorAltitudeUnitSwitch(coordinator),
            VevorHighAltitudeSwitch(coordinator),
        ]

        for switch in switches:
            assert switch._attr_icon is not None
            assert switch._attr_icon.startswith("mdi:")


# ---------------------------------------------------------------------------
# async_setup_entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry with different protocol modes."""

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_0_creates_all_entities(self):
        """Test protocol mode 0 (unknown) creates all entities as fallback."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 0

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 0: power + auto_offset + auto_start_stop + temp_unit + altitude_unit + high_altitude = 6
        assert len(entities) == 6

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_1_creates_core_only(self):
        """Test protocol mode 1 (AA55) creates only core switches."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 1

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 1: only power + auto_offset = 2
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_2_creates_core_only(self):
        """Test protocol mode 2 (AA55Encrypted) creates only core switches."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 2

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 2: only power + auto_offset = 2
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_4_creates_unit_switches(self):
        """Test protocol mode 4 (AA66Encrypted) creates unit switches."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 4

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 4: power + auto_offset + auto_start_stop + temp_unit + altitude_unit = 5
        assert len(entities) == 5

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_5_creates_abba_switches(self):
        """Test protocol mode 5 (ABBA) creates all including high altitude."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 5

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 5: power + auto_offset + auto_start_stop + temp_unit + altitude_unit + high_altitude = 6
        assert len(entities) == 6

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_6_creates_cbff_switches(self):
        """Test protocol mode 6 (CBFF) creates all except high altitude."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 6

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 6: power + auto_offset + auto_start_stop + temp_unit + altitude_unit = 5
        assert len(entities) == 5

    @pytest.mark.asyncio
    async def test_setup_entry_entity_types_mode_0(self):
        """Test entity types created for protocol mode 0."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 0

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        entity_types = [type(e).__name__ for e in entities]

        assert "VevorHeaterPowerSwitch" in entity_types
        assert "VevorAutoOffsetSwitch" in entity_types
        assert "VevorAutoStartStopSwitch" in entity_types
        assert "VevorTempUnitSwitch" in entity_types
        assert "VevorAltitudeUnitSwitch" in entity_types
        assert "VevorHighAltitudeSwitch" in entity_types


# ---------------------------------------------------------------------------
# _handle_coordinator_update tests
# ---------------------------------------------------------------------------

class TestHandleCoordinatorUpdate:
    """Tests for _handle_coordinator_update on all switch entities."""

    def test_power_switch_handle_coordinator_update(self):
        """Test PowerSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorHeaterPowerSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()

    def test_auto_start_stop_switch_handle_coordinator_update(self):
        """Test AutoStartStopSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoStartStopSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()

    def test_auto_offset_switch_handle_coordinator_update(self):
        """Test AutoOffsetSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorAutoOffsetSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()

    def test_temp_unit_switch_handle_coordinator_update(self):
        """Test TempUnitSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorTempUnitSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()

    def test_altitude_unit_switch_handle_coordinator_update(self):
        """Test AltitudeUnitSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorAltitudeUnitSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()

    def test_high_altitude_switch_handle_coordinator_update(self):
        """Test HighAltitudeSwitch _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        switch = VevorHighAltitudeSwitch(coordinator)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()

        switch.async_write_ha_state.assert_called_once()
