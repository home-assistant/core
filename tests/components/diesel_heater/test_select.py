"""Tests for Diesel Heater select platform."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import stubs first
from . import conftest  # noqa: F401

from custom_components.diesel_heater.select import (
    VevorHeaterModeSelect,
    VevorHeaterLanguageSelect,
    VevorHeaterPumpTypeSelect,
    VevorHeaterTankVolumeSelect,
    VevorBacklightSelect,
    async_setup_entry,
)


def create_mock_coordinator(protocol_mode: int = 1) -> MagicMock:
    """Create a mock coordinator for select testing.

    Args:
        protocol_mode: Protocol mode (1=AA55, 5=ABBA, etc.)
    """
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.protocol_mode = protocol_mode
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_set_mode = AsyncMock()
    coordinator.async_set_language = AsyncMock()
    coordinator.async_set_pump_type = AsyncMock()
    coordinator.async_set_tank_volume = AsyncMock()
    coordinator.async_set_backlight = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    coordinator.data = {
        "connected": True,
        "running_mode": 1,  # Level mode
        "running_step": 0,  # Standby
        "backlight": 3,
        "language": 0,  # English
        "pump_type": 1,  # 22µl
        "tank_volume": 2,  # 10 L
    }
    return coordinator


# ---------------------------------------------------------------------------
# Mode select tests
# ---------------------------------------------------------------------------

class TestVevorHeaterModeSelect:
    """Tests for Vevor heater mode select entity."""

    def test_current_option_level_mode(self):
        """Test current_option returns correct mode name."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_mode"] = 1  # Level mode
        select = VevorHeaterModeSelect(coordinator)

        # Should return some mode name
        assert select.current_option is not None

    def test_current_option_temp_mode(self):
        """Test current_option in temperature mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_mode"] = 2  # Temperature mode
        select = VevorHeaterModeSelect(coordinator)

        assert select.current_option is not None

    def test_current_option_none_when_no_data(self):
        """Test current_option returns None when no running_mode."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_mode"] = None
        select = VevorHeaterModeSelect(coordinator)

        assert select.current_option is None

    def test_options_not_empty(self):
        """Test options property is not empty."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) > 0

    def test_options_has_two_modes_for_non_abba(self):
        """Test options has exactly two modes for non-ABBA protocols."""
        coordinator = create_mock_coordinator(protocol_mode=1)  # AA55
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 2

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert "_running_mode" in select.unique_id

    def test_has_entity_name(self):
        """Test has_entity_name is True."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert select._attr_has_entity_name is True

    def test_device_info(self):
        """Test device_info is set correctly."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert select._attr_device_info is not None
        assert "identifiers" in select._attr_device_info

    @pytest.mark.asyncio
    async def test_async_select_option_level(self):
        """Test selecting level mode."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        # Get the level mode option name
        level_option = select.options[0]  # First option is Level
        await select.async_select_option(level_option)

        coordinator.async_set_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_select_option_temp(self):
        """Test selecting temperature mode."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        # Get the temperature mode option name
        temp_option = select.options[1]  # Second option is Temperature
        await select.async_select_option(temp_option)

        coordinator.async_set_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self):
        """Test selecting unknown mode does nothing."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        await select.async_select_option("Unknown Mode")

        coordinator.async_set_mode.assert_not_called()

    # ABBA Ventilation Mode tests (Issue #30)
    def test_abba_options_include_ventilation_when_standby(self):
        """Test ABBA protocol includes Ventilation option when in standby."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 0  # Standby
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 3
        assert "Ventilation" in select.options

    def test_abba_options_include_ventilation_when_already_ventilating(self):
        """Test ABBA protocol includes Ventilation when already ventilating."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 6  # Ventilation
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 3
        assert "Ventilation" in select.options

    def test_abba_options_exclude_ventilation_when_running(self):
        """Test ABBA protocol excludes Ventilation when heater is running."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 3  # Running
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 2
        assert "Ventilation" not in select.options

    def test_abba_options_exclude_ventilation_when_ignition(self):
        """Test ABBA protocol excludes Ventilation during ignition."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 2  # Ignition
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 2
        assert "Ventilation" not in select.options

    def test_abba_options_exclude_ventilation_when_cooldown(self):
        """Test ABBA protocol excludes Ventilation during cooldown."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 4  # Cooldown
        select = VevorHeaterModeSelect(coordinator)

        assert len(select.options) == 2
        assert "Ventilation" not in select.options

    def test_non_abba_never_shows_ventilation(self):
        """Test non-ABBA protocols never show Ventilation option."""
        for protocol in [1, 2, 4, 6]:  # AA55, AA55Encrypted, AA66, CBFF
            coordinator = create_mock_coordinator(protocol_mode=protocol)
            coordinator.data["running_step"] = 0  # Standby
            select = VevorHeaterModeSelect(coordinator)

            assert "Ventilation" not in select.options

    def test_current_option_ventilation_when_ventilating(self):
        """Test current_option returns Ventilation when running_step is ventilation."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 6  # Ventilation
        coordinator.data["running_mode"] = 1  # Level mode (should be overridden)
        select = VevorHeaterModeSelect(coordinator)

        assert select.current_option == "Ventilation"

    @pytest.mark.asyncio
    async def test_async_select_option_ventilation(self):
        """Test selecting ventilation mode for ABBA."""
        coordinator = create_mock_coordinator(protocol_mode=5)  # ABBA
        coordinator.data["running_step"] = 0  # Standby
        select = VevorHeaterModeSelect(coordinator)

        await select.async_select_option("Ventilation")

        coordinator.async_set_mode.assert_called_once_with(3)  # RUNNING_MODE_VENTILATION

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self):
        """Test async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)
        select.async_on_remove = MagicMock()

        await select.async_added_to_hass()

        coordinator.async_add_listener.assert_called_once()
        select.async_on_remove.assert_called_once()


# ---------------------------------------------------------------------------
# Language select tests
# ---------------------------------------------------------------------------

class TestVevorHeaterLanguageSelect:
    """Tests for Vevor heater language select entity."""

    def test_current_option_english(self):
        """Test current_option returns English."""
        coordinator = create_mock_coordinator()
        coordinator.data["language"] = 0  # English
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.current_option == "English"

    def test_current_option_german(self):
        """Test current_option returns German."""
        coordinator = create_mock_coordinator()
        coordinator.data["language"] = 2  # German
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.current_option == "German"

    def test_current_option_russian(self):
        """Test current_option returns Russian."""
        coordinator = create_mock_coordinator()
        coordinator.data["language"] = 4  # Russian
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.current_option == "Russian"

    def test_current_option_none_when_no_data(self):
        """Test current_option returns None when no language."""
        coordinator = create_mock_coordinator()
        coordinator.data["language"] = None
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.current_option is None

    def test_current_option_unknown_code(self):
        """Test current_option with unknown language code."""
        coordinator = create_mock_coordinator()
        coordinator.data["language"] = 99  # Unknown
        select = VevorHeaterLanguageSelect(coordinator)

        assert "Unknown" in select.current_option

    def test_options_not_empty(self):
        """Test _attr_options is not empty."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        assert len(select._attr_options) > 0

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        assert "_language" in select.unique_id

    def test_entity_category_is_set(self):
        """Test entity_category is set."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        # Just verify entity_category is set (it's a CONFIG category)
        assert select._attr_entity_category is not None

    @pytest.mark.asyncio
    async def test_async_select_option_english(self):
        """Test selecting English language."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        await select.async_select_option("English")

        coordinator.async_set_language.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_async_select_option_german(self):
        """Test selecting German language."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        await select.async_select_option("German")

        coordinator.async_set_language.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self):
        """Test selecting unknown language does nothing."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        await select.async_select_option("Unknown Language")

        coordinator.async_set_language.assert_not_called()

    def test_available_when_connected(self):
        """Test available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.available is True

    def test_unavailable_when_disconnected(self):
        """Test unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.available is False


# ---------------------------------------------------------------------------
# Pump type select tests
# ---------------------------------------------------------------------------

class TestVevorHeaterPumpTypeSelect:
    """Tests for Vevor heater pump type select entity."""

    def test_current_option_16ul(self):
        """Test current_option returns 16µl."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = 0  # 16µl
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option == "16µl"

    def test_current_option_22ul(self):
        """Test current_option returns 22µl."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = 1  # 22µl
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option == "22µl"

    def test_current_option_28ul(self):
        """Test current_option returns 28µl."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = 2  # 28µl
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option == "28µl"

    def test_current_option_32ul(self):
        """Test current_option returns 32µl."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = 3  # 32µl
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option == "32µl"

    def test_current_option_none_when_no_data(self):
        """Test current_option returns None when no pump_type."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = None
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option is None

    def test_current_option_unknown_type(self):
        """Test current_option with unknown pump type."""
        coordinator = create_mock_coordinator()
        coordinator.data["pump_type"] = 99  # Unknown
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert "Type 99" in select.current_option

    def test_options_not_empty(self):
        """Test _attr_options is not empty."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert len(select._attr_options) > 0

    def test_options_has_four_types(self):
        """Test _attr_options has four pump types."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert len(select._attr_options) == 4

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert "_pump_type" in select.unique_id

    @pytest.mark.asyncio
    async def test_async_select_option_16ul(self):
        """Test selecting 16µl pump type."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        await select.async_select_option("16µl")

        coordinator.async_set_pump_type.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_async_select_option_22ul(self):
        """Test selecting 22µl pump type."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        await select.async_select_option("22µl")

        coordinator.async_set_pump_type.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self):
        """Test selecting unknown pump type does nothing."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        await select.async_select_option("Unknown Pump")

        coordinator.async_set_pump_type.assert_not_called()

    def test_available_when_connected_and_pump_type_set(self):
        """Test available when connected and pump_type is set."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["pump_type"] = 1
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.available is True

    def test_unavailable_when_pump_type_none(self):
        """Test unavailable when pump_type is None (RF433 mode)."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        coordinator.data["pump_type"] = None
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.available is False


# ---------------------------------------------------------------------------
# Tank volume select tests
# ---------------------------------------------------------------------------

class TestVevorHeaterTankVolumeSelect:
    """Tests for Vevor heater tank volume select entity."""

    def test_current_option_none_volume(self):
        """Test current_option returns None (disabled)."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = 0  # None/disabled
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option == "None"

    def test_current_option_5l(self):
        """Test current_option returns 5 L."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = 1  # 5 L
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option == "5 L"

    def test_current_option_10l(self):
        """Test current_option returns 10 L."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = 2  # 10 L
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option == "10 L"

    def test_current_option_50l(self):
        """Test current_option returns 50 L."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = 10  # 50 L
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option == "50 L"

    def test_current_option_none_when_no_data(self):
        """Test current_option returns None when no tank_volume."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = None
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option is None

    def test_current_option_unknown_volume(self):
        """Test current_option with unknown volume shows raw value."""
        coordinator = create_mock_coordinator()
        coordinator.data["tank_volume"] = 99  # Unknown index
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert "99" in select.current_option

    def test_options_not_empty(self):
        """Test _attr_options is not empty."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert len(select._attr_options) > 0

    def test_options_has_11_volumes(self):
        """Test _attr_options has 11 volume options (0-10)."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert len(select._attr_options) == 11

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert "_tank_volume" in select.unique_id

    @pytest.mark.asyncio
    async def test_async_select_option_none(self):
        """Test selecting None (disabled)."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        await select.async_select_option("None")

        coordinator.async_set_tank_volume.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_async_select_option_5l(self):
        """Test selecting 5 L."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        await select.async_select_option("5 L")

        coordinator.async_set_tank_volume.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self):
        """Test selecting unknown volume does nothing."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        await select.async_select_option("Unknown Volume")

        coordinator.async_set_tank_volume.assert_not_called()

    def test_available_when_connected(self):
        """Test available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.available is True


# ---------------------------------------------------------------------------
# Backlight select tests
# ---------------------------------------------------------------------------

class TestVevorBacklightSelect:
    """Tests for Vevor backlight select entity."""

    def test_current_option_off(self):
        """Test current_option returns Off."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 0  # Off
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "Off"

    def test_current_option_level_3(self):
        """Test current_option returns level 3."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 3
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "3"

    def test_current_option_level_10(self):
        """Test current_option returns level 10."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 10
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "10"

    def test_current_option_level_50(self):
        """Test current_option returns level 50."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 50
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "50"

    def test_current_option_level_100(self):
        """Test current_option returns level 100."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 100
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "100"

    def test_current_option_none_when_no_data(self):
        """Test current_option returns None when no backlight."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = None
        select = VevorBacklightSelect(coordinator)

        assert select.current_option is None

    def test_current_option_unknown_value(self):
        """Test current_option with non-standard value shows raw number."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 15  # Not in options
        select = VevorBacklightSelect(coordinator)

        assert select.current_option == "15"

    def test_options_not_empty(self):
        """Test _attr_options is not empty."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        assert len(select._attr_options) > 0

    def test_unique_id(self):
        """Test unique_id format."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        assert "_backlight" in select.unique_id

    @pytest.mark.asyncio
    async def test_async_select_option_off(self):
        """Test selecting Off."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        await select.async_select_option("Off")

        coordinator.async_set_backlight.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_async_select_option_level_5(self):
        """Test selecting level 5."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        await select.async_select_option("5")

        coordinator.async_set_backlight.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_async_select_option_level_50(self):
        """Test selecting level 50."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        await select.async_select_option("50")

        coordinator.async_set_backlight.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self):
        """Test selecting unknown option does nothing."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        await select.async_select_option("Unknown")

        coordinator.async_set_backlight.assert_not_called()

    def test_available_when_backlight_set(self):
        """Test available when backlight is set."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = 5
        select = VevorBacklightSelect(coordinator)

        assert select.available is True

    def test_unavailable_when_backlight_none(self):
        """Test unavailable when backlight is None."""
        coordinator = create_mock_coordinator()
        coordinator.data["backlight"] = None
        select = VevorBacklightSelect(coordinator)

        assert select.available is False


# ---------------------------------------------------------------------------
# Availability tests
# ---------------------------------------------------------------------------

class TestSelectAvailability:
    """Tests for select availability."""

    def test_mode_available_when_connected(self):
        """Test mode select is available when connected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = True
        select = VevorHeaterModeSelect(coordinator)

        assert select.available is True

    def test_mode_unavailable_when_disconnected(self):
        """Test mode select is unavailable when disconnected."""
        coordinator = create_mock_coordinator()
        coordinator.data["connected"] = False
        select = VevorHeaterModeSelect(coordinator)

        assert select.available is False


# ---------------------------------------------------------------------------
# Entity attributes tests
# ---------------------------------------------------------------------------

class TestSelectEntityAttributes:
    """Tests for select entity attributes."""

    def test_mode_select_icon(self):
        """Test mode select has correct icon."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert select._attr_icon == "mdi:cog"

    def test_language_select_icon(self):
        """Test language select has correct icon."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        assert select._attr_icon == "mdi:translate"

    def test_pump_type_select_icon(self):
        """Test pump type select has correct icon."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select._attr_icon == "mdi:pump"

    def test_tank_volume_select_icon(self):
        """Test tank volume select has correct icon."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select._attr_icon == "mdi:gas-station"

    def test_backlight_select_icon(self):
        """Test backlight select has correct icon."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        assert select._attr_icon == "mdi:brightness-6"

    def test_mode_select_name(self):
        """Test mode select has correct name."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)

        assert select._attr_name == "Running Mode"

    def test_language_select_name(self):
        """Test language select has correct name."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        assert select._attr_name == "Language"

    def test_pump_type_select_name(self):
        """Test pump type select has correct name."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select._attr_name == "Pump Type"

    def test_tank_volume_select_name(self):
        """Test tank volume select has correct name."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select._attr_name == "Tank Volume"

    def test_backlight_select_name(self):
        """Test backlight select has correct name."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        assert select._attr_name == "Backlight"


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
        # Mode 0: mode + language + pump_type + tank_volume + backlight = 5
        assert len(entities) == 5

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_1_creates_mode_only(self):
        """Test protocol mode 1 (AA55) creates only mode select."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 1

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 1: only mode select
        assert len(entities) == 1
        assert isinstance(entities[0], VevorHeaterModeSelect)

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_2_creates_mode_and_backlight(self):
        """Test protocol mode 2 (AA55Encrypted) creates mode + backlight."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 2

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 2: mode + backlight = 2
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_4_creates_all_entities(self):
        """Test protocol mode 4 (AA66Encrypted) creates all entities."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 4

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 4: all 5 entities
        assert len(entities) == 5

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_5_creates_mode_only(self):
        """Test protocol mode 5 (ABBA) creates only mode select."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 5

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 5: only mode select
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_setup_entry_protocol_mode_6_creates_all_entities(self):
        """Test protocol mode 6 (CBFF) creates all entities."""
        coordinator = create_mock_coordinator()
        coordinator.protocol_mode = 6

        entry = MagicMock()
        entry.runtime_data = coordinator
        async_add_entities = MagicMock()
        hass = MagicMock()

        await async_setup_entry(hass, entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Mode 6: all 5 entities
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

        assert "VevorHeaterModeSelect" in entity_types
        assert "VevorHeaterLanguageSelect" in entity_types
        assert "VevorHeaterPumpTypeSelect" in entity_types
        assert "VevorHeaterTankVolumeSelect" in entity_types
        assert "VevorBacklightSelect" in entity_types


# ---------------------------------------------------------------------------
# _handle_coordinator_update tests
# ---------------------------------------------------------------------------

class TestHandleCoordinatorUpdate:
    """Tests for _handle_coordinator_update on all select entities."""

    def test_mode_select_handle_coordinator_update(self):
        """Test ModeSelect _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterModeSelect(coordinator)
        select.async_write_ha_state = MagicMock()

        select._handle_coordinator_update()

        select.async_write_ha_state.assert_called_once()

    def test_language_select_handle_coordinator_update(self):
        """Test LanguageSelect _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)
        select.async_write_ha_state = MagicMock()

        select._handle_coordinator_update()

        select.async_write_ha_state.assert_called_once()

    def test_pump_type_select_handle_coordinator_update(self):
        """Test PumpTypeSelect _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)
        select.async_write_ha_state = MagicMock()

        select._handle_coordinator_update()

        select.async_write_ha_state.assert_called_once()

    def test_tank_volume_select_handle_coordinator_update(self):
        """Test TankVolumeSelect _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)
        select.async_write_ha_state = MagicMock()

        select._handle_coordinator_update()

        select.async_write_ha_state.assert_called_once()

    def test_backlight_select_handle_coordinator_update(self):
        """Test BacklightSelect _handle_coordinator_update calls async_write_ha_state."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)
        select.async_write_ha_state = MagicMock()

        select._handle_coordinator_update()

        select.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# Additional async_added_to_hass tests
# ---------------------------------------------------------------------------

class TestAsyncAddedToHass:
    """Tests for async_added_to_hass on all select entities."""

    @pytest.mark.asyncio
    async def test_language_select_async_added_to_hass(self):
        """Test LanguageSelect async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)
        select.async_on_remove = MagicMock()

        await select.async_added_to_hass()

        coordinator.async_add_listener.assert_called_once()
        select.async_on_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_pump_type_select_async_added_to_hass(self):
        """Test PumpTypeSelect async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)
        select.async_on_remove = MagicMock()

        await select.async_added_to_hass()

        coordinator.async_add_listener.assert_called_once()
        select.async_on_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_tank_volume_select_async_added_to_hass(self):
        """Test TankVolumeSelect async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)
        select.async_on_remove = MagicMock()

        await select.async_added_to_hass()

        coordinator.async_add_listener.assert_called_once()
        select.async_on_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_backlight_select_async_added_to_hass(self):
        """Test BacklightSelect async_added_to_hass registers listener."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)
        select.async_on_remove = MagicMock()

        await select.async_added_to_hass()

        coordinator.async_add_listener.assert_called_once()
        select.async_on_remove.assert_called_once()


# ---------------------------------------------------------------------------
# Edge cases for current_option
# ---------------------------------------------------------------------------

class TestCurrentOptionEdgeCases:
    """Tests for edge cases in current_option properties."""

    def test_mode_select_unknown_mode_value(self):
        """Test ModeSelect with unknown mode value returns None."""
        coordinator = create_mock_coordinator()
        coordinator.data["running_mode"] = 99  # Unknown mode
        select = VevorHeaterModeSelect(coordinator)

        # RUNNING_MODE_NAMES.get(99) returns None
        assert select.current_option is None

    def test_mode_select_missing_running_mode_key(self):
        """Test ModeSelect when running_mode key is missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["running_mode"]
        select = VevorHeaterModeSelect(coordinator)

        assert select.current_option is None

    def test_language_select_missing_language_key(self):
        """Test LanguageSelect when language key is missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["language"]
        select = VevorHeaterLanguageSelect(coordinator)

        assert select.current_option is None

    def test_pump_type_select_missing_pump_type_key(self):
        """Test PumpTypeSelect when pump_type key is missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["pump_type"]
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select.current_option is None

    def test_tank_volume_select_missing_tank_volume_key(self):
        """Test TankVolumeSelect when tank_volume key is missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["tank_volume"]
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select.current_option is None

    def test_backlight_select_missing_backlight_key(self):
        """Test BacklightSelect when backlight key is missing."""
        coordinator = create_mock_coordinator()
        del coordinator.data["backlight"]
        select = VevorBacklightSelect(coordinator)

        assert select.current_option is None


# ---------------------------------------------------------------------------
# Device info tests
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    """Tests for device_info on all select entities."""

    def test_language_select_device_info(self):
        """Test LanguageSelect device_info is set correctly."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterLanguageSelect(coordinator)

        assert select._attr_device_info is not None
        assert "identifiers" in select._attr_device_info

    def test_pump_type_select_device_info(self):
        """Test PumpTypeSelect device_info is set correctly."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterPumpTypeSelect(coordinator)

        assert select._attr_device_info is not None
        assert "identifiers" in select._attr_device_info

    def test_tank_volume_select_device_info(self):
        """Test TankVolumeSelect device_info is set correctly."""
        coordinator = create_mock_coordinator()
        select = VevorHeaterTankVolumeSelect(coordinator)

        assert select._attr_device_info is not None
        assert "identifiers" in select._attr_device_info

    def test_backlight_select_device_info(self):
        """Test BacklightSelect device_info is set correctly."""
        coordinator = create_mock_coordinator()
        select = VevorBacklightSelect(coordinator)

        assert select._attr_device_info is not None
        assert "identifiers" in select._attr_device_info
