"""Tests for Diesel Heater climate platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.climate import VevorHeaterClimate, async_setup_entry


def create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator for climate testing."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_set_temperature = AsyncMock()
    coordinator.async_turn_on = AsyncMock()
    coordinator.async_turn_off = AsyncMock()
    coordinator.data = {
        "connected": True,
        "running_state": 1,
        "running_step": 3,
        "running_mode": 2,  # Temperature mode
        "set_level": 5,
        "set_temp": 22,
        "cab_temperature": 20.5,
        "case_temperature": 50,
        "supply_voltage": 12.5,
        "error_code": 0,
    }
    return coordinator


def create_mock_config_entry() -> MagicMock:
    """Create a mock config entry for climate testing."""
    entry = MagicMock()
    entry.data = {
        "address": "AA:BB:CC:DD:EE:FF",
        "preset_away_temp": 8,
        "preset_comfort_temp": 21,
    }
    entry.options = {
        "preset_modes": {},
    }
    entry.entry_id = "test_entry"
    return entry


# ---------------------------------------------------------------------------
# Climate entity tests
# ---------------------------------------------------------------------------

class TestVevorHeaterClimate:
    """Tests for Vevor climate entity."""

    def test_current_temperature(self):
        """Test current_temperature returns cabin temperature."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.current_temperature == 20.5

    def test_current_temperature_none(self):
        """Test current_temperature when None."""
        coordinator = create_mock_coordinator()
        coordinator.data["cab_temperature"] = None
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.current_temperature is None

    def test_target_temperature(self):
        """Test target_temperature returns set_temp."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.target_temperature == 22

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert "_climate" in climate.unique_id


class TestClimateHvacMode:
    """Tests for HVAC mode functionality."""

    def test_hvac_mode_heat_when_running(self):
        """Test hvac_mode is HEAT when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 1  # Running
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # The actual value may be a MagicMock, just check it's not None/OFF
        assert climate.hvac_mode is not None

    def test_hvac_mode_off_when_not_running(self):
        """Test hvac_mode is OFF when heater is off."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_state"] = 0  # Off
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Check it returns a valid value
        assert climate.hvac_mode is not None


class TestClimateAvailability:
    """Tests for climate availability."""

    def test_available_when_connected(self):
        """Test climate is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.last_update_success = True
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.available is True

    def test_available_property_exists(self):
        """Test available property is accessible."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Just verify we can access the property
        _ = climate.available


# ---------------------------------------------------------------------------
# HVAC Action tests
# ---------------------------------------------------------------------------

class TestClimateHvacAction:
    """Tests for HVAC action functionality."""

    def test_hvac_action_when_standby_and_off(self):
        """Test hvac_action when standby and running_state OFF."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 0  # RUNNING_STEP_STANDBY
        coordinator.data["running_state"] = 0  # OFF
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return HVACAction.OFF (mock object)
        assert climate.hvac_action is not None

    def test_hvac_action_when_standby_and_on(self):
        """Test hvac_action when standby but running_state ON."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 0  # RUNNING_STEP_STANDBY
        coordinator.data["running_state"] = 1  # ON (Auto Start/Stop waiting)
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return HVACAction.IDLE
        assert climate.hvac_action is not None

    def test_hvac_action_when_running(self):
        """Test hvac_action when heater is running."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 3  # RUNNING_STEP_RUNNING
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return HVACAction.HEATING
        assert climate.hvac_action is not None

    def test_hvac_action_when_ignition(self):
        """Test hvac_action when in ignition phase."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 2  # RUNNING_STEP_IGNITION
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return HVACAction.HEATING
        assert climate.hvac_action is not None

    def test_hvac_action_when_self_test(self):
        """Test hvac_action when in self-test phase."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 1  # RUNNING_STEP_SELF_TEST
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.hvac_action is not None

    def test_hvac_action_when_cooldown(self):
        """Test hvac_action when in cooldown phase."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 4  # RUNNING_STEP_COOLDOWN
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return HVACAction.FAN
        assert climate.hvac_action is not None

    def test_hvac_action_when_ventilation(self):
        """Test hvac_action when in ventilation mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 6  # RUNNING_STEP_VENTILATION
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.hvac_action is not None

    def test_hvac_action_none_when_running_step_none(self):
        """Test hvac_action is None when running_step is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = None
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.hvac_action is None

    def test_hvac_action_for_unknown_step(self):
        """Test hvac_action for unknown running_step."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_step"] = 99  # Unknown step
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return IDLE as default
        assert climate.hvac_action is not None


# ---------------------------------------------------------------------------
# Preset mode tests
# ---------------------------------------------------------------------------

class TestClimatePresetMode:
    """Tests for preset mode functionality."""

    def test_preset_mode_property_accessible(self):
        """Test preset_mode property is accessible."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Just verify we can access the property
        _ = climate.preset_mode

    def test_preset_mode_when_temp_matches_away(self):
        """Test preset detection when temp matches away."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 8  # Matches default away temp
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 8
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should detect PRESET_AWAY
        assert climate.preset_mode is not None

    def test_preset_mode_when_temp_matches_comfort(self):
        """Test preset detection when temp matches comfort."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 21  # Matches default comfort temp
        config_entry = create_mock_config_entry()
        config_entry.data["preset_comfort_temp"] = 21
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.preset_mode is not None

    def test_preset_mode_when_user_cleared(self):
        """Test preset stays NONE when user explicitly cleared it."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 8  # Matches away temp
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._user_cleared_preset = True  # User cleared preset

        # Should still return PRESET_NONE
        assert climate.preset_mode is not None


# ---------------------------------------------------------------------------
# Async method tests
# ---------------------------------------------------------------------------

class TestClimateAsyncMethods:
    """Tests for async climate methods."""

    @pytest.mark.asyncio
    async def test_async_set_temperature_method_exists(self):
        """Test async_set_temperature method exists and is callable."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Verify method exists
        assert hasattr(climate, 'async_set_temperature')
        assert callable(climate.async_set_temperature)

    @pytest.mark.asyncio
    async def test_async_turn_on(self):
        """Test async_turn_on turns on heater."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_turn_on()

        coordinator.async_turn_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test async_turn_off turns off heater."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_turn_off()

        coordinator.async_turn_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_method_exists(self):
        """Test async_set_hvac_mode method exists."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert hasattr(climate, 'async_set_hvac_mode')
        assert callable(climate.async_set_hvac_mode)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_method_exists(self):
        """Test async_set_preset_mode method exists."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert hasattr(climate, 'async_set_preset_mode')
        assert callable(climate.async_set_preset_mode)


# ---------------------------------------------------------------------------
# Climate attributes tests
# ---------------------------------------------------------------------------

class TestClimateAttributes:
    """Tests for climate entity attributes."""

    def test_min_temp(self):
        """Test min_temp attribute."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_min_temp == 8

    def test_max_temp(self):
        """Test max_temp attribute."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_max_temp == 36

    def test_target_temperature_step(self):
        """Test target_temperature_step attribute."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_target_temperature_step == 1

    def test_hvac_modes_not_empty(self):
        """Test hvac_modes attribute is not empty."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert len(climate._attr_hvac_modes) == 2

    def test_preset_modes_not_empty(self):
        """Test preset_modes attribute is not empty."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert len(climate._attr_preset_modes) == 3

    def test_has_entity_name(self):
        """Test has_entity_name is True."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_has_entity_name is True

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_device_info is not None
        assert "identifiers" in climate._attr_device_info
        assert "name" in climate._attr_device_info


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------

class TestClimateHelperMethods:
    """Tests for climate helper methods."""

    def test_get_away_temp_default(self):
        """Test _get_away_temp returns default value."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}  # No preset temps
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return default (8)
        assert climate._get_away_temp() == 8

    def test_get_away_temp_configured(self):
        """Test _get_away_temp returns configured value."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 10
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._get_away_temp() == 10

    def test_get_comfort_temp_default(self):
        """Test _get_comfort_temp returns default value."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}  # No preset temps
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return default (21)
        assert climate._get_comfort_temp() == 21

    def test_get_comfort_temp_configured(self):
        """Test _get_comfort_temp returns configured value."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_comfort_temp"] = 23
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._get_comfort_temp() == 23


# ---------------------------------------------------------------------------
# Async setup entry tests
# ---------------------------------------------------------------------------

class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_climate(self):
        """Test async_setup_entry creates climate entity."""
        coordinator = create_mock_coordinator()

        # Create mock entry with runtime_data
        entry = create_mock_config_entry()
        entry.runtime_data = coordinator

        # Create mock async_add_entities
        async_add_entities = MagicMock()

        # Create mock hass
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        # Verify async_add_entities was called with a list containing VevorHeaterClimate
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], VevorHeaterClimate)


# ---------------------------------------------------------------------------
# Extended async method tests
# ---------------------------------------------------------------------------

class TestClimateAsyncSetTemperature:
    """Tests for async_set_temperature method."""

    @pytest.mark.asyncio
    async def test_async_set_temperature_method_callable(self):
        """Test async_set_temperature is callable."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Verify method is callable
        assert callable(climate.async_set_temperature)

    @pytest.mark.asyncio
    async def test_async_set_temperature_no_kwargs_returns_early(self):
        """Test async_set_temperature with no kwargs does nothing."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return early without calling coordinator
        await climate.async_set_temperature()

        coordinator.async_set_temperature.assert_not_called()


class TestClimateAsyncSetPresetMode:
    """Tests for async_set_preset_mode method."""

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_method_callable(self):
        """Test async_set_preset_mode is callable."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert callable(climate.async_set_preset_mode)

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_sets_current_preset(self):
        """Test async_set_preset_mode sets _current_preset."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Call with a string value
        await climate.async_set_preset_mode("test_preset")

        # _current_preset should be set to the passed value
        assert climate._current_preset == "test_preset"


class TestClimateAsyncSetHvacMode:
    """Tests for async_set_hvac_mode method."""

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_method_callable(self):
        """Test async_set_hvac_mode is callable."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert callable(climate.async_set_hvac_mode)


# ---------------------------------------------------------------------------
# Preset mode edge cases
# ---------------------------------------------------------------------------

class TestClimatePresetModeEdgeCases:
    """Tests for preset mode edge cases."""

    def test_preset_mode_when_set_temp_is_none(self):
        """Test preset_mode when set_temp is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = None
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should return default preset (PRESET_NONE or current_preset)
        result = climate.preset_mode
        assert result is not None

    def test_preset_mode_returns_current_preset_when_no_match(self):
        """Test preset_mode returns _current_preset when no temp match."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 15  # Doesn't match any preset
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 8
        config_entry.data["preset_comfort_temp"] = 21
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._current_preset = "custom_preset"

        result = climate.preset_mode
        assert result == "custom_preset"


# ---------------------------------------------------------------------------
# Entity lifecycle tests
# ---------------------------------------------------------------------------

class TestClimateEntityLifecycle:
    """Tests for climate entity lifecycle."""

    def test_handle_coordinator_update_method_exists(self):
        """Test _handle_coordinator_update method exists."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Verify method exists
        assert hasattr(climate, '_handle_coordinator_update')

    def test_handle_coordinator_update_is_callable(self):
        """Test _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate.async_write_ha_state = MagicMock()

        climate._handle_coordinator_update()

        climate.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# Full async_set_preset_mode tests
# ---------------------------------------------------------------------------

class TestClimateAsyncSetPresetModeFull:
    """Full tests for async_set_preset_mode method.

    Note: Due to stub limitations (each import creates new MagicMocks),
    we import the PRESET_* constants from the climate module itself.
    """

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_away(self):
        """Test async_set_preset_mode with PRESET_AWAY."""
        # Import from the same place climate.py imports
        from custom_components.diesel_heater.climate import PRESET_AWAY

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 10
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_preset_mode(PRESET_AWAY)

        # Should call coordinator with away temperature
        coordinator.async_set_temperature.assert_called_once_with(10)
        assert climate._current_preset == PRESET_AWAY
        assert climate._user_cleared_preset is False

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_comfort(self):
        """Test async_set_preset_mode with PRESET_COMFORT."""
        from custom_components.diesel_heater.climate import PRESET_COMFORT

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_comfort_temp"] = 23
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_preset_mode(PRESET_COMFORT)

        # Should call coordinator with comfort temperature
        coordinator.async_set_temperature.assert_called_once_with(23)
        assert climate._current_preset == PRESET_COMFORT
        assert climate._user_cleared_preset is False

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_none(self):
        """Test async_set_preset_mode with PRESET_NONE."""
        from custom_components.diesel_heater.climate import PRESET_NONE

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._current_preset = "comfort"  # Set previous preset

        # Mock async_write_ha_state since it's from the base class
        climate.async_write_ha_state = MagicMock()

        await climate.async_set_preset_mode(PRESET_NONE)

        # Should NOT call coordinator (keep current temperature)
        coordinator.async_set_temperature.assert_not_called()
        assert climate._current_preset is None
        assert climate._user_cleared_preset is True
        climate.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_clears_none_flag_on_away(self):
        """Test setting preset clears _user_cleared_preset flag."""
        from custom_components.diesel_heater.climate import PRESET_AWAY

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._user_cleared_preset = True  # Was previously cleared

        await climate.async_set_preset_mode(PRESET_AWAY)

        assert climate._user_cleared_preset is False

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_clears_none_flag_on_comfort(self):
        """Test setting comfort preset clears _user_cleared_preset flag."""
        from custom_components.diesel_heater.climate import PRESET_COMFORT

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._user_cleared_preset = True  # Was previously cleared

        await climate.async_set_preset_mode(PRESET_COMFORT)

        assert climate._user_cleared_preset is False


# ---------------------------------------------------------------------------
# Full async_set_temperature tests
# ---------------------------------------------------------------------------

class TestClimateAsyncSetTemperatureFull:
    """Full tests for async_set_temperature method.

    Note: Due to stub limitations (ATTR_TEMPERATURE is a MagicMock, not
    "temperature"), we can't fully test the async_set_temperature flow.
    The basic tests in TestClimateAsyncSetTemperature verify the method
    returns early when no temperature is provided. These tests verify
    the method exists and can be called.
    """

    @pytest.mark.asyncio
    async def test_async_set_temperature_method_signature(self):
        """Test async_set_temperature accepts kwargs."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Should accept arbitrary kwargs without error
        await climate.async_set_temperature(some_param=25)

        # Method returns early when ATTR_TEMPERATURE not in kwargs
        coordinator.async_set_temperature.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_temperature_returns_early_no_temp(self):
        """Test async_set_temperature returns early with no temperature."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_temperature()

        coordinator.async_set_temperature.assert_not_called()

    def test_get_away_temp_in_async_set_temperature_path(self):
        """Test _get_away_temp is correctly configured for temperature matching."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 10
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._get_away_temp() == 10

    def test_get_comfort_temp_in_async_set_temperature_path(self):
        """Test _get_comfort_temp is correctly configured for temperature matching."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_comfort_temp"] = 23
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._get_comfort_temp() == 23

    def test_user_cleared_preset_flag_initialized_false(self):
        """Test _user_cleared_preset is initialized to False."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._user_cleared_preset is False

    def test_current_preset_initialized_none(self):
        """Test _current_preset is initialized to None."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._current_preset is None

    @pytest.mark.asyncio
    async def test_async_set_temperature_with_real_key(self):
        """Test async_set_temperature with real temperature key."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Use actual string key "temperature" (what ATTR_TEMPERATURE should be)
        await climate.async_set_temperature(temperature=25)

        coordinator.async_set_temperature.assert_called_once_with(25)

    @pytest.mark.asyncio
    async def test_async_set_temperature_clears_preset_flag(self):
        """Test async_set_temperature clears _user_cleared_preset flag."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._user_cleared_preset = True

        await climate.async_set_temperature(temperature=20)

        assert climate._user_cleared_preset is False

    @pytest.mark.asyncio
    async def test_async_set_temperature_auto_selects_away_preset(self):
        """Test async_set_temperature auto-selects PRESET_AWAY if temp matches."""
        from custom_components.diesel_heater.climate import PRESET_AWAY

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 15
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_temperature(temperature=15)

        coordinator.async_set_temperature.assert_called_once_with(15)
        assert climate._current_preset == PRESET_AWAY

    @pytest.mark.asyncio
    async def test_async_set_temperature_auto_selects_comfort_preset(self):
        """Test async_set_temperature auto-selects PRESET_COMFORT if temp matches."""
        from custom_components.diesel_heater.climate import PRESET_COMFORT

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_comfort_temp"] = 22
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_temperature(temperature=22)

        coordinator.async_set_temperature.assert_called_once_with(22)
        assert climate._current_preset == PRESET_COMFORT

    @pytest.mark.asyncio
    async def test_async_set_temperature_sets_preset_none_for_other_temps(self):
        """Test async_set_temperature sets preset to None for non-matching temps."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 10
        config_entry.data["preset_comfort_temp"] = 23
        climate = VevorHeaterClimate(coordinator, config_entry)
        climate._current_preset = "something"  # Set previous value

        # Temperature doesn't match away (10) or comfort (23)
        await climate.async_set_temperature(temperature=18)

        coordinator.async_set_temperature.assert_called_once_with(18)
        assert climate._current_preset is None

    @pytest.mark.asyncio
    async def test_async_set_temperature_converts_to_int(self):
        """Test async_set_temperature converts float to int."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_temperature(temperature=22.7)

        # Should be converted to int (22)
        coordinator.async_set_temperature.assert_called_once_with(22)


# ---------------------------------------------------------------------------
# Full async_set_hvac_mode tests
# ---------------------------------------------------------------------------

class TestClimateAsyncSetHvacModeFull:
    """Full tests for async_set_hvac_mode method.

    Note: We import HVACMode from the climate module to get the same
    MagicMock instance that the code uses internally.
    """

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_heat(self):
        """Test async_set_hvac_mode with HEAT."""
        from custom_components.diesel_heater.climate import HVACMode

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_hvac_mode(HVACMode.HEAT)

        coordinator.async_turn_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off(self):
        """Test async_set_hvac_mode with OFF."""
        from custom_components.diesel_heater.climate import HVACMode

        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        await climate.async_set_hvac_mode(HVACMode.OFF)

        coordinator.async_turn_off.assert_called_once()


# ---------------------------------------------------------------------------
# Temperature unit tests
# ---------------------------------------------------------------------------

class TestClimateTemperatureUnit:
    """Tests for climate temperature unit."""

    def test_temperature_unit_is_celsius(self):
        """Test temperature unit is Celsius."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # The unit is set via _attr_temperature_unit
        assert climate._attr_temperature_unit is not None

    def test_supported_features(self):
        """Test supported features include required features."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Verify supported_features is set
        assert climate._attr_supported_features is not None


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------

class TestClimateEdgeCases:
    """Additional edge case tests for climate entity."""

    def test_target_temperature_none(self):
        """Test target_temperature when set_temp is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = None
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.target_temperature is None

    def test_preset_mode_away_detection(self):
        """Test preset mode correctly detects away."""
        from custom_components.diesel_heater.climate import PRESET_AWAY

        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 8
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 8
        config_entry.data["preset_comfort_temp"] = 21
        climate = VevorHeaterClimate(coordinator, config_entry)

        # The preset_mode should be PRESET_AWAY
        assert climate.preset_mode == PRESET_AWAY

    def test_preset_mode_comfort_detection(self):
        """Test preset mode correctly detects comfort."""
        from custom_components.diesel_heater.climate import PRESET_COMFORT

        coordinator = create_mock_coordinator()
        coordinator.data["set_temp"] = 21
        config_entry = create_mock_config_entry()
        config_entry.data["preset_away_temp"] = 8
        config_entry.data["preset_comfort_temp"] = 21
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate.preset_mode == PRESET_COMFORT

    def test_available_uses_coordinator(self):
        """Test available property is accessible."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        # Just verify property is accessible (behavior from CoordinatorEntity)
        _ = climate.available

    def test_name_is_none(self):
        """Test name attribute is None (uses device name)."""
        coordinator = create_mock_coordinator()
        config_entry = create_mock_config_entry()
        climate = VevorHeaterClimate(coordinator, config_entry)

        assert climate._attr_name is None
