"""Tests for Diesel Heater number platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.number import (
    VevorHeaterLevelNumber,
    VevorHeaterTemperatureNumber,
    VevorHeaterOffsetNumber,
    VevorTankCapacityNumber,
    async_setup_entry,
)


def create_mock_coordinator(protocol_mode: int = 0) -> MagicMock:
    """Create a mock coordinator for number testing."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_set_level = AsyncMock()
    coordinator.async_set_temperature = AsyncMock()
    coordinator.async_set_heater_offset = AsyncMock()
    coordinator.async_set_tank_capacity = AsyncMock()
    coordinator.protocol_mode = protocol_mode
    coordinator.data = {
        "connected": True,
        "set_level": 5,
        "set_temp": 22,
        "heater_offset": 0,
        "tank_capacity": 5,
    }
    return coordinator


# ---------------------------------------------------------------------------
# Level number tests
# ---------------------------------------------------------------------------

class TestVevorHeaterLevelNumber:
    """Tests for Vevor heater level number entity."""

    def test_native_value(self):
        """Test native_value returns current level."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 7
        number = VevorHeaterLevelNumber(coordinator)

        assert number.native_value == 7

    def test_min_value_attr(self):
        """Test _attr_native_min_value is 1."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        assert number._attr_native_min_value == 1

    def test_max_value_attr(self):
        """Test _attr_native_max_value is 10."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        assert number._attr_native_max_value == 10

    def test_step_attr(self):
        """Test _attr_native_step is 1."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        assert number._attr_native_step == 1

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        assert "_level" in number.unique_id


# ---------------------------------------------------------------------------
# Offset number tests
# ---------------------------------------------------------------------------

class TestVevorHeaterOffsetNumber:
    """Tests for Vevor heater offset number entity."""

    def test_native_value(self):
        """Test native_value returns current offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["heater_offset"] = 2
        number = VevorHeaterOffsetNumber(coordinator)

        assert number.native_value == 2

    def test_native_value_negative(self):
        """Test native_value with negative offset."""
        coordinator = create_mock_coordinator()
        coordinator.data["heater_offset"] = -3
        number = VevorHeaterOffsetNumber(coordinator)

        assert number.native_value == -3

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)

        assert "_offset" in number.unique_id


# ---------------------------------------------------------------------------
# Tank capacity number tests
# ---------------------------------------------------------------------------

class TestVevorTankCapacityNumber:
    """Tests for Vevor tank capacity number entity."""

    def test_native_value(self):
        """Test native_value returns current tank capacity."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_capacity"] = 10
        number = VevorTankCapacityNumber(coordinator)

        assert number.native_value == 10

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)

        assert "_tank" in number.unique_id or "_capacity" in number.unique_id


# ---------------------------------------------------------------------------
# Availability tests
# ---------------------------------------------------------------------------

class TestNumberAvailability:
    """Tests for number availability."""

    def test_available_when_connected(self):
        """Test number is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        number = VevorHeaterLevelNumber(coordinator)

        assert number.available is True

    def test_available_property_exists(self):
        """Test available property is accessible."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        # Just verify property is accessible
        _ = number.available


# ---------------------------------------------------------------------------
# Async setup entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_core_entities(self):
        """Test async_setup_entry creates core number entities."""
        coordinator = create_mock_coordinator(protocol_mode=0)

        # Create mock entry with runtime_data
        entry = MagicMock()
        entry.runtime_data = coordinator

        # Create mock async_add_entities
        async_add_entities = MagicMock()

        # Create mock hass
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        # Verify async_add_entities was called
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 0 creates all entities (4 total)
        assert len(call_args) == 4

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_2(self):
        """Test async_setup_entry with protocol mode 2 includes offset."""
        coordinator = create_mock_coordinator(protocol_mode=2)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 2 includes offset
        assert len(call_args) == 4

    @pytest.mark.asyncio
    async def test_async_setup_entry_protocol_mode_1(self):
        """Test async_setup_entry with protocol mode 1 excludes offset."""
        coordinator = create_mock_coordinator(protocol_mode=1)

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        # Mode 1 excludes offset (only 3 entities)
        assert len(call_args) == 3


# ---------------------------------------------------------------------------
# Temperature number tests
# ---------------------------------------------------------------------------

class TestVevorHeaterTemperatureNumber:
    """Tests for Vevor heater temperature number entity."""

    def test_native_value(self):
        """Test native_value returns current temperature."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 25
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number.native_value == 25

    def test_native_value_none_returns_min(self):
        """Test native_value returns min temp when None."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = None
        number = VevorHeaterTemperatureNumber(coordinator)

        # Should return MIN_TEMP_CELSIUS (8)
        assert number.native_value == 8

    def test_min_value_attr(self):
        """Test _attr_native_min_value is 8."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number._attr_native_min_value == 8

    def test_max_value_attr(self):
        """Test _attr_native_max_value is 36."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number._attr_native_max_value == 36

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert "_target_temp" in number.unique_id

    def test_has_entity_name(self):
        """Test has_entity_name is True."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number._attr_has_entity_name is True

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number._attr_device_info is not None
        assert "identifiers" in number._attr_device_info


# ---------------------------------------------------------------------------
# Async set native value tests
# ---------------------------------------------------------------------------

class TestNumberAsyncSetNativeValue:
    """Tests for async_set_native_value methods."""

    @pytest.mark.asyncio
    async def test_level_async_set_native_value(self):
        """Test VevorHeaterLevelNumber async_set_native_value."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        await number.async_set_native_value(7)

        coordinator.async_set_level.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_temperature_async_set_native_value(self):
        """Test VevorHeaterTemperatureNumber async_set_native_value."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        await number.async_set_native_value(25)

        coordinator.async_set_temperature.assert_called_once_with(25)

    @pytest.mark.asyncio
    async def test_offset_async_set_native_value(self):
        """Test VevorHeaterOffsetNumber async_set_native_value."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)

        await number.async_set_native_value(3)

        coordinator.async_set_heater_offset.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_tank_capacity_async_set_native_value(self):
        """Test VevorTankCapacityNumber async_set_native_value."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)

        await number.async_set_native_value(15)

        coordinator.async_set_tank_capacity.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_level_converts_float_to_int(self):
        """Test level async_set_native_value converts float to int."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        await number.async_set_native_value(5.7)

        coordinator.async_set_level.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_offset_handles_negative_value(self):
        """Test offset async_set_native_value handles negative values."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)

        await number.async_set_native_value(-5)

        coordinator.async_set_heater_offset.assert_called_once_with(-5)


# ---------------------------------------------------------------------------
# Entity attribute tests
# ---------------------------------------------------------------------------

class TestNumberEntityAttributes:
    """Tests for number entity attributes."""

    def test_level_icon(self):
        """Test level icon."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)

        assert number._attr_icon == "mdi:gauge"

    def test_temperature_icon(self):
        """Test temperature icon."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)

        assert number._attr_icon == "mdi:thermometer"

    def test_offset_icon(self):
        """Test offset icon."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)

        assert number._attr_icon == "mdi:thermometer-plus"

    def test_tank_capacity_icon(self):
        """Test tank capacity icon."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)

        assert number._attr_icon == "mdi:gas-station"

    def test_offset_min_max_values(self):
        """Test offset min/max values."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)

        assert number._attr_native_min_value == -9
        assert number._attr_native_max_value == 9

    def test_tank_capacity_min_max_values(self):
        """Test tank capacity min/max values."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)

        assert number._attr_native_min_value == 1
        assert number._attr_native_max_value == 100

    def test_tank_capacity_entity_category(self):
        """Test tank capacity is in CONFIG category."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)

        # EntityCategory.CONFIG is mocked, just check it's set
        assert number._attr_entity_category is not None


# ---------------------------------------------------------------------------
# _handle_coordinator_update tests
# ---------------------------------------------------------------------------

class TestHandleCoordinatorUpdate:
    """Tests for _handle_coordinator_update on all number entities."""

    def test_level_handle_coordinator_update(self):
        """Test LevelNumber _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterLevelNumber(coordinator)
        number.async_write_ha_state = MagicMock()

        number._handle_coordinator_update()

        number.async_write_ha_state.assert_called_once()

    def test_temperature_handle_coordinator_update(self):
        """Test TemperatureNumber _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterTemperatureNumber(coordinator)
        number.async_write_ha_state = MagicMock()

        number._handle_coordinator_update()

        number.async_write_ha_state.assert_called_once()

    def test_offset_handle_coordinator_update(self):
        """Test OffsetNumber _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        number = VevorHeaterOffsetNumber(coordinator)
        number.async_write_ha_state = MagicMock()

        number._handle_coordinator_update()

        number.async_write_ha_state.assert_called_once()

    def test_tank_capacity_handle_coordinator_update(self):
        """Test TankCapacityNumber _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        number = VevorTankCapacityNumber(coordinator)
        number.async_write_ha_state = MagicMock()

        number._handle_coordinator_update()

        number.async_write_ha_state.assert_called_once()
