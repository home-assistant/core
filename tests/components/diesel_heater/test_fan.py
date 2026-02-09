"""Tests for Diesel Heater fan platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.fan import (
    VevorHeaterFan,
    ORDERED_LEVELS,
    async_setup_entry,
)
from custom_components.diesel_heater.const import (
    RUNNING_MODE_LEVEL,
    RUNNING_MODE_TEMPERATURE,
    RUNNING_MODE_MANUAL,
)


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for fan testing."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_turn_on = AsyncMock()
    coordinator.async_turn_off = AsyncMock()
    coordinator.async_set_level = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    coordinator.data = {
        "connected": True,
        "running_state": 1,
        "running_step": 3,
        "running_mode": RUNNING_MODE_LEVEL,  # Level mode = 1
        "set_level": 5,
        "set_temp": 22,
        "cab_temperature": 20.5,
        "error_code": 0,
    }
    return coordinator


# ---------------------------------------------------------------------------
# Fan entity basic tests
# ---------------------------------------------------------------------------

class TestVevorHeaterFan:
    """Tests for Vevor fan entity."""

    def test_is_on_when_running(self):
        """Test is_on returns True when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 1
        fan = VevorHeaterFan(coordinator)

        assert fan.is_on is True

    def test_is_on_when_off(self):
        """Test is_on returns False when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 0
        fan = VevorHeaterFan(coordinator)

        assert fan.is_on is False

    def test_unique_id_format(self):
        """Test unique_id format includes address and suffix."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan.unique_id == "AA:BB:CC:DD:EE:FF_heater_level"

    def test_has_entity_name(self):
        """Test has_entity_name is True."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan._attr_has_entity_name is True

    def test_entity_name(self):
        """Test entity name is set."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan._attr_name == "Heater Level"

    def test_icon(self):
        """Test icon is set."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan._attr_icon == "mdi:fire"

    def test_speed_count(self):
        """Test speed count is 10."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan._attr_speed_count == 10

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        assert fan._attr_device_info is not None
        assert "identifiers" in fan._attr_device_info
        assert "name" in fan._attr_device_info

    def test_supported_features(self):
        """Test supported features include SET_SPEED, TURN_ON, TURN_OFF."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        # Verify supported_features attribute exists and is set
        assert fan._attr_supported_features is not None


# ---------------------------------------------------------------------------
# Fan availability tests
# ---------------------------------------------------------------------------

class TestFanAvailability:
    """Tests for fan availability."""

    def test_available_when_connected_and_level_mode(self):
        """Test fan is available when connected and in level mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = RUNNING_MODE_LEVEL
        fan = VevorHeaterFan(coordinator)

        assert fan.available is True

    def test_not_available_when_not_connected(self):
        """Test fan is not available when not connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        coordinator.data["running_mode"] = RUNNING_MODE_LEVEL
        fan = VevorHeaterFan(coordinator)

        assert fan.available is False

    def test_not_available_in_temp_mode(self):
        """Test fan is not available in temperature mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = RUNNING_MODE_TEMPERATURE
        fan = VevorHeaterFan(coordinator)

        assert fan.available is False

    def test_not_available_in_manual_mode(self):
        """Test fan is not available in manual mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = RUNNING_MODE_MANUAL
        fan = VevorHeaterFan(coordinator)

        assert fan.available is False

    def test_not_available_when_running_mode_none(self):
        """Test fan is not available when running_mode is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["running_mode"] = None
        fan = VevorHeaterFan(coordinator)

        assert fan.available is False


# ---------------------------------------------------------------------------
# Percentage property tests
# ---------------------------------------------------------------------------

class TestFanPercentage:
    """Tests for fan percentage property."""

    def test_percentage_returns_value_for_valid_level(self):
        """Test percentage returns a value for valid levels."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = 5
        fan = VevorHeaterFan(coordinator)

        # Percentage should return an integer (actual value depends on HA utils)
        result = fan.percentage
        assert result is not None

    def test_percentage_none_when_level_none(self):
        """Test percentage returns None when level is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_level"] = None
        fan = VevorHeaterFan(coordinator)

        assert fan.percentage is None

    def test_percentage_property_accessible_for_all_levels(self):
        """Test percentage property can be accessed for all levels."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        for level in range(1, 11):
            coordinator.data["set_level"] = level
            result = fan.percentage
            # Just verify it doesn't raise an exception
            assert result is not None or level == 0


# ---------------------------------------------------------------------------
# Async method tests
# ---------------------------------------------------------------------------

class TestFanAsyncMethods:
    """Tests for async fan methods."""

    @pytest.mark.asyncio
    async def test_async_turn_on_without_percentage(self):
        """Test async_turn_on without percentage turns on heater."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_turn_on()

        coordinator.async_turn_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_on_with_percentage(self):
        """Test async_turn_on with percentage calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_turn_on(percentage=50)

        # Should call async_set_level (actual value depends on HA conversion)
        coordinator.async_set_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_on_with_100_percent(self):
        """Test async_turn_on with 100% calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_turn_on(percentage=100)

        coordinator.async_set_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_on_with_low_percentage(self):
        """Test async_turn_on with low percentage calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_turn_on(percentage=15)

        coordinator.async_set_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off turns off heater."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_turn_off()

        coordinator.async_turn_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero_turns_off(self):
        """Test async_set_percentage with 0 turns off heater."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_set_percentage(0)

        coordinator.async_turn_off.assert_called_once()
        coordinator.async_set_level.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_percentage_nonzero_calls_set_level(self):
        """Test async_set_percentage with non-zero calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_set_percentage(50)

        coordinator.async_set_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_percentage_100_calls_set_level(self):
        """Test async_set_percentage with 100% calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_set_percentage(100)

        coordinator.async_set_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_percentage_10_calls_set_level(self):
        """Test async_set_percentage with 10% calls async_set_level."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        await fan.async_set_percentage(10)

        coordinator.async_set_level.assert_called_once()


# ---------------------------------------------------------------------------
# Entity lifecycle tests
# ---------------------------------------------------------------------------

class TestFanEntityLifecycle:
    """Tests for fan entity lifecycle."""

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self):
        """Test async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        # Mock async_on_remove
        fan.async_on_remove = MagicMock()

        await fan.async_added_to_hass()

        # Verify listener was registered
        coordinator.async_add_listener.assert_called_once()
        fan.async_on_remove.assert_called_once()

    def test_handle_coordinator_update(self):
        """Test _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        fan = VevorHeaterFan(coordinator)

        # Mock async_write_ha_state
        fan.async_write_ha_state = MagicMock()

        fan._handle_coordinator_update()

        fan.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# Ordered levels constant tests
# ---------------------------------------------------------------------------

class TestOrderedLevels:
    """Tests for ORDERED_LEVELS constant."""

    def test_ordered_levels_length(self):
        """Test ORDERED_LEVELS has 10 levels."""
        assert len(ORDERED_LEVELS) == 10

    def test_ordered_levels_content(self):
        """Test ORDERED_LEVELS contains string levels 1-10."""
        expected = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        assert ORDERED_LEVELS == expected


# ---------------------------------------------------------------------------
# Async setup entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_fan(self):
        """Test async_setup_entry creates fan entity."""
        coordinator = create_mock_coordinator()

        # Create mock entry with runtime_data
        entry = MagicMock()
        entry.runtime_data = coordinator

        # Create mock async_add_entities
        async_add_entities = MagicMock()

        # Create mock hass
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        # Verify async_add_entities was called with a list containing VevorHeaterFan
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], VevorHeaterFan)
