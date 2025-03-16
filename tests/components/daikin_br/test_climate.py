"""Tests for the Daikin Climate custom component."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from pyiotdevice import InvalidDataException
import pytest

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SWING_OFF,
    SWING_VERTICAL,
    HVACMode,
)
from homeassistant.components.daikin_br.climate import DaikinClimate, async_setup_entry
from homeassistant.components.daikin_br.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant


# pylint: disable=redefined-outer-name, too-few-public-methods
# pylint: disable=too-many-instance-attributes, too-many-lines
# pylint: disable=protected-access
@pytest.fixture
def dummy_coordinator(hass: HomeAssistant):
    """Create a dummy coordinator for testing purposes."""
    coordinator = MagicMock()
    coordinator.data = {"port1": {"fw_ver": "1.0.0"}}
    coordinator.hass = hass
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_config_entry(dummy_coordinator):
    """Fixture to create a valid Home Assistant config entry with runtime_data."""
    entry_data = {
        "device_apn": "TEST_APN",
        "host": "192.168.1.100",
        "api_key": "VALID_KEY",
        "device_name": "TEST DEVICE",
    }

    entry = MagicMock(spec=ConfigEntry)
    entry.domain = DOMAIN
    entry.data = entry_data
    entry.unique_id = "test_entry_id"
    entry.entry_id = "mock_entry_id"
    entry.source = "user"
    entry.runtime_data = dummy_coordinator  # Set runtime_data for access in tests

    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that async_setup_entry sets up the climate entity."""
    # Create a dummy async_add_entities as a MagicMock instead of AsyncMock
    async_add_entities = MagicMock()

    # Ensure that the runtime_data on the config entry (provided by mock_config_entry)
    # has an async_request_refresh method.
    mock_config_entry.runtime_data.async_request_refresh = AsyncMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify that async_add_entities was called correctly
    async_add_entities.assert_called_once()
    args, _kwargs = async_add_entities.call_args
    assert isinstance(args[0], list)
    assert len(args[0]) == 1
    climate_entity = args[0][0]
    assert isinstance(climate_entity, DaikinClimate)

    # Verify that the coordinator's async_request_refresh was awaited
    mock_config_entry.runtime_data.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_set_hvac_mode(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test setting various HVAC modes in DaikinClimate."""
    # Create the DaikinClimate entity using the config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass  # Ensure hass is set on the entity

    # Patch set_thing_state to be an AsyncMock.
    climate_entity.set_thing_state = AsyncMock()

    # Define expected HVAC mode mappings and corresponding JSON payloads.
    test_cases = {
        HVACMode.OFF: json.dumps({"port1": {"power": 0}}),
        HVACMode.FAN_ONLY: json.dumps({"port1": {"mode": 6, "power": 1}}),
        HVACMode.COOL: json.dumps({"port1": {"mode": 3, "power": 1}}),
        HVACMode.DRY: json.dumps({"port1": {"mode": 2, "power": 1}}),
        HVACMode.HEAT: json.dumps({"port1": {"mode": 4, "power": 1}}),
        HVACMode.AUTO: json.dumps({"port1": {"mode": 1, "power": 1}}),
    }

    # Test each valid HVAC mode.
    for hvac_mode, expected_json in test_cases.items():
        await climate_entity.async_set_hvac_mode(hvac_mode)
        climate_entity.set_thing_state.assert_awaited_once_with(expected_json)
        climate_entity.set_thing_state.reset_mock()

    # Test an unsupported HVAC mode.
    await climate_entity.async_set_hvac_mode("INVALID_MODE")
    assert "Unsupported HVAC mode: INVALID_MODE" in caplog.text
    assert climate_entity.set_thing_state.call_count == 0


@pytest.mark.asyncio
async def test_async_set_fan_mode(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test setting various fan modes in DaikinClimate."""
    # Initialize DaikinClimate instance using the mock config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch set_thing_state to be an AsyncMock.
    climate_entity.set_thing_state = AsyncMock()

    # Set log capture level.
    caplog.set_level("DEBUG")

    # --- Test valid fan modes when HVAC mode is COOL ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.COOL)
    assert climate_entity.hvac_mode == HVACMode.COOL, (
        f"Expected HVAC mode COOL, got {climate_entity.hvac_mode}"
    )

    test_cases = {
        "auto": {"port1": {"fan": 17}},
        "high": {"port1": {"fan": 7}},
        "medium_high": {"port1": {"fan": 6}},
        "medium": {"port1": {"fan": 5}},
        "low_medium": {"port1": {"fan": 4}},
        "low": {"port1": {"fan": 3}},
        "quiet": {"port1": {"fan": 18}},
    }

    for fan_mode, expected_data in test_cases.items():
        expected_json = json.dumps(expected_data)
        await climate_entity.async_set_fan_mode(fan_mode)
        climate_entity.set_thing_state.assert_called_once_with(expected_json)
        climate_entity.set_thing_state.reset_mock()

    # --- Test fan mode change when HVAC mode is DRY (should not send command) ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.DRY)
    assert climate_entity.hvac_mode == HVACMode.DRY, (
        f"Expected HVAC mode DRY, got {climate_entity.hvac_mode}"
    )
    caplog.clear()
    await climate_entity.async_set_fan_mode("medium")
    # Assert that no command is sent when in DRY mode.
    assert climate_entity.set_thing_state.call_count == 0

    # --- Test unsupported fan mode when HVAC mode is COOL ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.COOL)
    caplog.clear()
    await climate_entity.async_set_fan_mode("INVALID_MODE")
    # Assert that no command is sent.
    assert climate_entity.set_thing_state.call_count == 0
    # Assert that an error log was recorded.
    assert any("Unsupported fan mode" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_async_set_temperature(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test setting various temperature values in DaikinClimate."""
    # Create the climate entity using the mock config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch set_thing_state (which sends the command) and async_write_ha_state.
    climate_entity.set_thing_state = AsyncMock()
    climate_entity.async_write_ha_state = MagicMock()

    caplog.set_level("DEBUG")

    # --- Test valid temperature in COOL mode ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.COOL)
    valid_temp = 22
    expected_json = json.dumps({"port1": {"temperature": valid_temp}})
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: valid_temp})
    climate_entity.set_thing_state.assert_called_once_with(expected_json)
    climate_entity.set_thing_state.reset_mock()

    # --- Test temperature below range in COOL mode ---
    caplog.clear()
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 10})
    # No command should be sent if temperature is out of range.
    climate_entity.set_thing_state.assert_not_called()

    # --- Test temperature above range in COOL mode ---
    caplog.clear()
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 35})
    climate_entity.set_thing_state.assert_not_called()

    # --- Test temperature setting in FAN_ONLY mode (should not send command) ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.FAN_ONLY)
    caplog.clear()
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 24})
    climate_entity.set_thing_state.assert_not_called()

    # --- Test temperature setting in DRY mode (should not send command) ---
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.DRY)
    caplog.clear()
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 25})
    climate_entity.set_thing_state.assert_not_called()

    # --- Test missing temperature attribute ---
    caplog.clear()
    await climate_entity.async_set_temperature()
    climate_entity.set_thing_state.assert_not_called()


@pytest.mark.asyncio
async def test_async_set_preset_mode(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test setting preset modes in DaikinClimate."""
    # Create DaikinClimate instance using the mock config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch schedule_update_ha_state (synchronous) and set_thing_state (async).
    climate_entity.schedule_update_ha_state = MagicMock()
    climate_entity.set_thing_state = AsyncMock()

    caplog.set_level("DEBUG")

    # --- Test when device is ON ---
    # Simulate device is ON by setting the internal _power_state.
    monkeypatch.setattr(climate_entity, "_power_state", 1)

    # Test preset ECO.
    expected_json_eco = json.dumps({"port1": {"powerchill": 0, "econo": 1}})
    await climate_entity.async_set_preset_mode(PRESET_ECO)
    # Use the public property to verify the preset mode.
    assert climate_entity.preset_mode == PRESET_ECO
    climate_entity.schedule_update_ha_state.assert_called_once()
    climate_entity.set_thing_state.assert_awaited_once_with(expected_json_eco)
    climate_entity.schedule_update_ha_state.reset_mock()
    climate_entity.set_thing_state.reset_mock()

    # Test preset BOOST.
    expected_json_boost = json.dumps({"port1": {"powerchill": 1, "econo": 0}})
    await climate_entity.async_set_preset_mode(PRESET_BOOST)
    assert climate_entity.preset_mode == PRESET_BOOST
    climate_entity.schedule_update_ha_state.assert_called_once()
    climate_entity.set_thing_state.assert_awaited_once_with(expected_json_boost)
    climate_entity.schedule_update_ha_state.reset_mock()
    climate_entity.set_thing_state.reset_mock()

    # Test preset NONE.
    expected_json_none = json.dumps({"port1": {"powerchill": 0, "econo": 0}})
    await climate_entity.async_set_preset_mode(PRESET_NONE)
    assert climate_entity.preset_mode == PRESET_NONE
    climate_entity.schedule_update_ha_state.assert_called_once()
    climate_entity.set_thing_state.assert_awaited_once_with(expected_json_none)
    climate_entity.schedule_update_ha_state.reset_mock()
    climate_entity.set_thing_state.reset_mock()

    # --- Test when device is OFF ---
    monkeypatch.setattr(climate_entity, "_power_state", 0)
    caplog.clear()
    await climate_entity.async_set_preset_mode(PRESET_ECO)
    # Expect that no command is sent when the device is off.
    climate_entity.schedule_update_ha_state.assert_not_called()
    climate_entity.set_thing_state.assert_not_called()


@pytest.mark.asyncio
async def test_async_set_swing_mode(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test setting swing modes in DaikinClimate."""
    # Create the DaikinClimate entity using the config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch set_thing_state to be an AsyncMock.
    climate_entity.set_thing_state = AsyncMock()

    caplog.set_level("DEBUG")

    # Ensure the available swing modes are set as expected.
    monkeypatch.setattr(
        climate_entity, "_attr_swing_modes", {SWING_VERTICAL, SWING_OFF}
    )

    # --- Test valid swing mode: SWING_VERTICAL ---
    expected_json_vertical = json.dumps({"port1": {"v_swing": 1}})
    await climate_entity.async_set_swing_mode(SWING_VERTICAL)
    climate_entity.set_thing_state.assert_awaited_once_with(expected_json_vertical)
    climate_entity.set_thing_state.reset_mock()

    # --- Test valid swing mode: SWING_OFF ---
    expected_json_off = json.dumps({"port1": {"v_swing": 0}})
    await climate_entity.async_set_swing_mode(SWING_OFF)
    climate_entity.set_thing_state.assert_awaited_once_with(expected_json_off)
    climate_entity.set_thing_state.reset_mock()

    # --- Test unsupported swing mode ---
    caplog.clear()
    await climate_entity.async_set_swing_mode("INVALID_MODE")
    # Verify that an error is logged indicating an unsupported swing mode.
    assert any(
        "Unsupported swing mode: INVALID_MODE" in record.message
        for record in caplog.records
    ), "Expected 'Unsupported swing mode: INVALID_MODE' in logs"
    climate_entity.set_thing_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_thing_state_success(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that set_thing_state updates the entity state as expected."""
    # Use the config entry fixture that already has runtime_data set.
    entry = mock_config_entry

    # Instantiate the DaikinClimate entity using the full config entry.
    climate_entity = DaikinClimate(entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch async_write_ha_state so that no actual update is performed.
    climate_entity.async_write_ha_state = MagicMock()

    # Define the expected response from async_send_operation_data.
    # This response should update internal state accordingly.
    mock_response = {
        "port1": {
            "power": 1,
            "mode": 3,  # Should map to HVACMode.COOL
            "temperature": 22,
            "sensors": {"room_temp": 23},
            "fan": 5,  # Should map to "medium" (per your mapping)
            "v_swing": 1,  # Should yield SWING_VERTICAL (assume "vertical")
            "econo": 1,  # Should set preset mode to PRESET_ECO (assume "eco")
            "powerchill": 0,
        }
    }

    # Patch async_send_operation_data so that it returns our mock response.
    with patch(
        "homeassistant.components.daikin_br.climate.async_send_operation_data",
        new=AsyncMock(return_value=mock_response),
    ):
        payload = json.dumps({"port1": {"temperature": 22}})
        await climate_entity.set_thing_state(payload)

    # Now verify the updated state via the public properties.
    assert climate_entity.power_state == 1, (
        f"Expected power_state 1, got {climate_entity.power_state}"
    )
    assert climate_entity.hvac_mode == HVACMode.COOL, (
        f"Expected HVACMode.COOL, got {climate_entity.hvac_mode}"
    )
    assert climate_entity.target_temperature == 22, (
        f"Expected target_temperature 22, got {climate_entity.target_temperature}"
    )
    assert climate_entity.current_temperature == 23, (
        f"Expected current_temperature 23, got {climate_entity.current_temperature}"
    )
    # For fan_mode, a value of 5 should map to "medium" according to your mapping.
    assert climate_entity.fan_mode == "medium", (
        f"Expected fan_mode 'medium', got {climate_entity.fan_mode}"
    )
    # For swing_mode, a value of 1 should yield SWING_VERTICAL.
    assert climate_entity.swing_mode == SWING_VERTICAL, (
        f"Expected swing_mode '{SWING_VERTICAL}', got {climate_entity.swing_mode}"
    )
    # For preset_mode, econo=1 and powerchill=0 should yield PRESET_ECO.
    assert climate_entity.preset_mode == PRESET_ECO, (
        f"Expected preset_mode '{PRESET_ECO}', got {climate_entity.preset_mode}"
    )

    # Verify that async_write_ha_state was called once.
    climate_entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_update_entity_properties(mock_config_entry) -> None:
    """Test that update_entity_properties updates internal state correctly."""
    # Instantiate the DaikinClimate entity using the config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    # Ensure hass is set on the entity (if not already set by the fixture).
    climate_entity.hass = MagicMock()

    # Patch async_write_ha_state to avoid side effects.
    climate_entity.async_write_ha_state = MagicMock()

    # --- Test branch 1: When econo is 1 (preset ECO) ---
    status1 = {
        "port1": {
            "sensors": {"room_temp": 23},
            "temperature": 22,
            "power": 1,
            "mode": 3,  # Mode 3 should map to HVACMode.COOL
            "fan": 5,  # Fan value 5 should map to "medium" (per your mapping)
            "v_swing": 1,  # v_swing 1 should yield SWING_VERTICAL
            "econo": 1,  # Should set preset mode to PRESET_ECO
            "powerchill": 0,
        }
    }
    climate_entity.update_entity_properties(status1)
    # Verify public properties via getters.
    assert climate_entity.current_temperature == 23
    assert climate_entity.target_temperature == 22
    assert climate_entity.power_state == 1
    assert climate_entity.hvac_mode == HVACMode.COOL
    assert climate_entity.fan_mode == "medium"
    assert climate_entity.swing_mode == SWING_VERTICAL
    assert climate_entity.preset_mode == PRESET_ECO
    climate_entity.async_write_ha_state.assert_called_once()

    # --- Test branch 2: When powerchill is 1 (preset BOOST) ---
    climate_entity.async_write_ha_state.reset_mock()
    status2 = {
        "port1": {
            "sensors": {"room_temp": 24},
            "temperature": 23,
            "power": 1,
            "mode": 3,
            "fan": 5,
            "v_swing": 1,
            "econo": 0,
            "powerchill": 1,
        }
    }
    climate_entity.update_entity_properties(status2)
    assert climate_entity.preset_mode == PRESET_BOOST
    climate_entity.async_write_ha_state.assert_called_once()

    # --- Test branch 3: When both econo and powerchill are 0 (preset NONE) ---
    climate_entity.async_write_ha_state.reset_mock()
    status3 = {
        "port1": {
            "sensors": {"room_temp": 25},
            "temperature": 24,
            "power": 1,
            "mode": 3,
            "fan": 5,
            "v_swing": 1,
            "econo": 0,
            "powerchill": 0,
        }
    }
    climate_entity.update_entity_properties(status3)
    assert climate_entity.preset_mode == PRESET_NONE
    climate_entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_update_entity_properties_device_off(
    mock_config_entry, hass: HomeAssistant
) -> None:
    """Test update_entity_properties when the device is OFF."""
    # Create the DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass

    # Patch async_write_ha_state to avoid side effects.
    climate_entity.async_write_ha_state = MagicMock()

    # Simulate port_status data indicating the device is OFF.
    port_status = {
        "port1": {
            "sensors": {"room_temp": 23},
            "temperature": 22,
            "power": 0,  # Device is OFF
            "mode": 0,  # Expected to map to HVACMode.OFF
            "fan": 3,  # Fan speed 3 should map to "low" per your mapping
            "v_swing": 0,  # 0 -> SWING_OFF
            "econo": 0,  # No economy mode
            "powerchill": 0,  # No powerchill
        }
    }

    # Call update_entity_properties.
    climate_entity.update_entity_properties(port_status)

    # Verify that the public properties reflect the expected state.
    assert climate_entity.current_temperature == 23, (
        f"Expected current_temperature 23, got {climate_entity.current_temperature}"
    )
    assert climate_entity.target_temperature == 22, (
        f"Expected target_temperature 22, got {climate_entity.target_temperature}"
    )
    assert climate_entity.power_state == 0, (
        f"Expected power_state 0, got {climate_entity.power_state}"
    )
    assert climate_entity.hvac_mode == HVACMode.OFF, (
        f"Expected HVACMode.OFF, got {climate_entity.hvac_mode}"
    )
    # Assuming your mapping converts fan value 3 to "low".
    assert climate_entity.fan_mode == "low", (
        f"Expected fan_mode 'low', got {climate_entity.fan_mode}"
    )
    assert climate_entity.swing_mode == SWING_OFF, (
        f"Expected swing_mode {SWING_OFF}, got {climate_entity.swing_mode}"
    )
    assert climate_entity.preset_mode == PRESET_NONE, (
        f"Expected preset_mode {PRESET_NONE}, got {climate_entity.preset_mode}"
    )

    # Verify that async_write_ha_state was called once.
    climate_entity.async_write_ha_state.assert_called_once()


@pytest.mark.parametrize(
    ("hvac_value", "expected_mode"),
    [
        (0, HVACMode.OFF),
        (6, HVACMode.FAN_ONLY),
        (3, HVACMode.COOL),
        (2, HVACMode.DRY),
        (4, HVACMode.HEAT),
        (1, HVACMode.AUTO),
        (99, HVACMode.OFF),  # Unknown value should default to HVACMode.OFF
    ],
)
def test_map_hvac_mode(mock_config_entry, hvac_value, expected_mode) -> None:
    """Test map_hvac_mode method.

    This ensures that device-specific HVAC mode values are correctly mapped
    to Home Assistant HVAC modes.
    """
    # Create a DaikinClimate instance using the mock_config_entry.
    climate_entity = DaikinClimate(mock_config_entry)
    # Call map_hvac_mode and check that it returns the expected mode.
    assert climate_entity.map_hvac_mode(hvac_value) == expected_mode


@pytest.mark.parametrize(
    ("fan_value", "expected_mode"),
    [
        (17, "auto"),
        (7, "high"),
        (6, "medium_high"),
        (5, "medium"),
        (4, "low_medium"),
        (3, "low"),
        (18, "quiet"),
        (99, "auto"),  # Unknown value should default to "auto"
    ],
)
def test_map_fan_speed(mock_config_entry, fan_value, expected_mode) -> None:
    """Test map_fan_speed method for correct fan speed mappings.

    This ensures that the device-specific fan speed values are correctly mapped
    to Home Assistant fan mode strings.
    """
    # Create a DaikinClimate instance using the valid config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    # Call map_fan_speed and check that it returns the expected mode.
    assert climate_entity.map_fan_speed(fan_value) == expected_mode


@pytest.mark.parametrize(
    ("temperature", "expected_temperature"),
    [
        (22, 22),  # Valid temperature.
        (30, 30),  # Valid upper limit.
        (16, 16),  # Valid lower limit.
        (50, 50),  # Extreme value (assuming no validation).
        (None, None),  # Edge case: None input.
    ],
)
def test_target_temperature_property(
    temperature, expected_temperature, mock_config_entry
) -> None:
    """Test that update_entity_properties sets the target temperature correctly.

    A dummy device status dict with only the "temperature" key is used.
    """
    # Create the DaikinClimate entity using the mock config entry.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = MagicMock()
    climate_entity.async_write_ha_state = MagicMock()

    # Build a dummy status dict simulating a device response with the given temperature.
    dummy_status = {"port1": {"temperature": temperature}}

    # Call update_entity_properties to update the internal state.
    climate_entity.update_entity_properties(dummy_status)

    # Assert that the public target_temperature property equals the expected value.
    assert climate_entity.target_temperature == expected_temperature


@pytest.mark.parametrize(
    ("swing_mode", "expected_swing_mode"),
    [
        (SWING_OFF, SWING_OFF),  # Swing off.
        (SWING_VERTICAL, SWING_VERTICAL),  # Vertical swing.
    ],
)
def test_swing_mode_property(
    monkeypatch: pytest.MonkeyPatch, swing_mode, expected_swing_mode, mock_config_entry
) -> None:
    """Test that the swing_mode property returns the correct swing mode."""
    # Create the DaikinClimate instance using the mock_config_entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)

    # Use monkeypatch to override the underlying protected swing mode attribute.
    monkeypatch.setattr(climate_entity, "_attr_swing_mode", swing_mode)

    # Assert that the public swing_mode property returns the expected swing mode.
    assert climate_entity.swing_mode == expected_swing_mode


@pytest.mark.parametrize(
    ("preset_mode", "expected_preset_mode"),
    [
        (PRESET_ECO, PRESET_ECO),  # Economy mode.
        (PRESET_BOOST, PRESET_BOOST),  # Power chill mode.
        (PRESET_NONE, PRESET_NONE),  # No preset mode.
    ],
)
def test_preset_mode_property(
    monkeypatch: pytest.MonkeyPatch,
    preset_mode,
    expected_preset_mode,
    mock_config_entry,
) -> None:
    """Test that the preset_mode property returns the correct value."""
    # Create a DaikinClimate instance using the mock_config_entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)

    # Override the underlying preset mode attribute.
    monkeypatch.setattr(climate_entity, "_attr_preset_mode", preset_mode)

    # Assert that the public preset_mode property returns the expected value.
    assert climate_entity.preset_mode == expected_preset_mode


def test_property_getters(mock_config_entry) -> None:
    """Test the property getters of DaikinClimate."""
    # Create the DaikinClimate entity using the mock_config_entry fixture.
    # The mock_config_entry fixture provides an entry with device_apn "TEST_APN",
    # host "192.168.1.100", api_key "VALID_KEY", device_name "TEST DEVICE", etc.
    climate_entity = DaikinClimate(mock_config_entry)

    # Verify that properties are derived correctly from the config entry.
    assert climate_entity.translation_key == "daikin_ac"
    assert climate_entity.unique_id == "TEST_APN"
    assert climate_entity.name is None
    assert climate_entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert climate_entity.min_temp == 10.0
    assert climate_entity.max_temp == 32.0
    assert climate_entity.target_temperature_step == 1.0


def test_device_info(mock_config_entry) -> None:
    """Test the device_info property of DaikinClimate."""
    # Create the DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)

    # Expected values based on our config entry data.
    expected_identifiers = {(DOMAIN, "TEST_APN")}
    expected_name = "TEST DEVICE"
    expected_manufacturer = "Daikin"
    expected_model = "Smart AC Series"
    # Our fixture doesn't set a firmware version so we expect None.
    expected_sw_version = None

    # Retrieve the device_info property.
    device_info = climate_entity.device_info

    # Instead of checking instance type (since DeviceInfo is a TypedDict),
    # verify that device_info is a dict and contains the expected keys and values.
    assert isinstance(device_info, dict)
    assert device_info.get("identifiers") == expected_identifiers
    assert device_info.get("name") == expected_name
    assert device_info.get("manufacturer") == expected_manufacturer
    assert device_info.get("model") == expected_model
    assert device_info.get("sw_version") == expected_sw_version


@pytest.mark.asyncio
async def test_set_thing_state_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test that set_thing_state logs an error when async_send_operation_data fails."""
    # Create the DaikinClimate entity using the config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    entity.entity_id = "climate.test_device"

    # Patch async_write_ha_state to avoid actual HA state updates.
    entity.async_write_ha_state = MagicMock()

    caplog.set_level(logging.DEBUG)

    # Patch async_send_operation_data to simulate an error.
    with patch(
        "homeassistant.components.daikin_br.climate.async_send_operation_data",
        new=AsyncMock(side_effect=Exception("Simulated error")),
    ):
        # Call set_thing_state with a dummy payload.
        await entity.set_thing_state(json.dumps({"port1": {"temperature": 22}}))

    # Verify that the error message was logged.
    assert "Failed to send command: Simulated error" in caplog.text


@pytest.mark.asyncio
async def test_async_set_preset_mode_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test unsupported preset mode."""
    # Create the DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Use monkeypatch to simulate that the device is ON.
    monkeypatch.setattr(climate_entity, "_power_state", 1)

    # Patch schedule_update_ha_state (synchronous) and set_thing_state (async).
    climate_entity.schedule_update_ha_state = MagicMock()
    climate_entity.set_thing_state = AsyncMock()

    caplog.clear()

    # Call async_set_preset_mode with an unsupported preset value.
    await climate_entity.async_set_preset_mode("INVALID_PRESET")

    # Assert that an error log is produced.
    assert any(
        "Unsupported preset mode: INVALID_PRESET" in record.message
        for record in caplog.records
    ), f"Expected error log but got: {caplog.text}"

    # Ensure that neither schedule_update_ha_state nor set_thing_state was called.
    climate_entity.schedule_update_ha_state.assert_not_called()
    climate_entity.set_thing_state.assert_not_called()


@pytest.mark.asyncio
async def test_handle_coordinator_update_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test that _handle_coordinator_update marks the entity as unavailable.

    When update_entity_properties fails.
    """
    # Create a DaikinClimate entity using the config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    entity.entity_id = "climate.test_entity"

    # Patch update_entity_properties to raise an exception.
    entity.update_entity_properties = MagicMock(side_effect=Exception("Test exception"))

    # Simulate a coordinator update by calling the update handler.
    entity._handle_coordinator_update()

    # Verify that the entity is marked as unavailable.
    assert entity._attr_available is False

    # Verify that an error was logged.
    assert any(
        "Error updating entity properties" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_async_set_hvac_mode_unsupported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test unsupported HVAC mode."""
    # Create the DaikinClimate entity using the config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass

    # Patch set_thing_state to be an AsyncMock.
    entity.set_thing_state = AsyncMock()

    # Call async_set_hvac_mode with an unsupported mode.
    await entity.async_set_hvac_mode("INVALID_MODE")

    # Verify that the error message is logged.
    assert "Unsupported HVAC mode: INVALID_MODE" in caplog.text
    # Ensure that set_thing_state was not called.
    entity.set_thing_state.assert_not_called()


@pytest.mark.asyncio
async def test_async_set_fan_mode_unsupported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test unsupported fan mode."""
    # Create the DaikinClimate entity using the mock config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    entity.set_thing_state = AsyncMock()

    # Call async_set_fan_mode with an invalid fan mode.
    await entity.async_set_fan_mode("INVALID_FAN")

    # Check that the expected error log is produced.
    assert "Unsupported fan mode" in caplog.text
    # Verify that no command was sent.
    entity.set_thing_state.assert_not_called()


@pytest.mark.asyncio
async def test_async_set_temperature_in_dry(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that setting temperature in DRY mode does not send a command."""
    # Create a DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch async_write_ha_state and set_thing_state.
    climate_entity.async_write_ha_state = MagicMock()
    climate_entity.set_thing_state = AsyncMock()

    # Use monkeypatch to set the internal _hvac_mode to HVACMode.DRY.
    monkeypatch.setattr(climate_entity, "_hvac_mode", HVACMode.DRY)

    # Call async_set_temperature with a test temperature value.
    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 25})

    # Verify that set_thing_state was not called.
    climate_entity.set_thing_state.assert_not_called()

    # Assert that the target_temperature property returns the expected value.
    assert climate_entity.target_temperature == 25


@pytest.mark.asyncio
async def test_set_thing_state_preset_boost_and_none(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that set_thing_state updates the preset mode correctly.

    First, when powerchill equals 1, the preset mode should be PRESET_BOOST.
    Then, when both econo and powerchill equal 0, the preset mode should be PRESET_NONE.
    """
    # Create the DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"

    # Patch async_write_ha_state to avoid actual HA updates.
    climate_entity.async_write_ha_state = MagicMock()

    # Prepare a dummy payload (its content is irrelevant here).
    payload = json.dumps({"port1": {"temperature": 22}})

    # Create two dummy responses:
    # Response that should trigger PRESET_BOOST.
    response_boost = {
        "port1": {
            "power": 1,
            "mode": 3,  # COOL mode (for example)
            "temperature": 22,
            "sensors": {"room_temp": 23},
            "fan": 5,
            "v_swing": 1,
            "econo": 0,
            "powerchill": 1,  # This should set preset mode to PRESET_BOOST.
        }
    }
    # Response that should trigger PRESET_NONE.
    response_none = {
        "port1": {
            "power": 1,
            "mode": 3,
            "temperature": 22,
            "sensors": {"room_temp": 23},
            "fan": 5,
            "v_swing": 1,
            "econo": 0,
            "powerchill": 0,  # This should set preset mode to PRESET_NONE.
        }
    }

    # Patch async_send_operation_data to return our dummy responses sequentially.
    with patch(
        "homeassistant.components.daikin_br.climate.async_send_operation_data",
        new=AsyncMock(side_effect=[response_boost, response_none]),
    ):
        # First call: Expect preset mode to be PRESET_BOOST.
        await climate_entity.set_thing_state(payload)
        assert climate_entity.preset_mode == PRESET_BOOST

        # Second call: Expect preset mode to be PRESET_NONE.
        await climate_entity.set_thing_state(payload)
        assert climate_entity.preset_mode == PRESET_NONE


@pytest.mark.asyncio
async def test_set_thing_state_preset_boost(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that set_thing_state updates the preset mode to PRESET_BOOST.

    When the response indicates that powerchill equals 1.
    """
    # Create the DaikinClimate entity using the config entry fixture.
    climate_entity = DaikinClimate(mock_config_entry)
    climate_entity.hass = hass
    climate_entity.entity_id = "climate.test_device"
    # Patch async_write_ha_state so that no real HA update is attempted.
    climate_entity.async_write_ha_state = MagicMock()

    # Prepare a dummy response where econo=0 and powerchill=1.
    mock_response = {
        "port1": {
            "power": 1,
            "mode": 3,  # For example, COOL mode.
            "temperature": 22,
            "sensors": {"room_temp": 23},
            "fan": 5,  # Should map to "medium" per your mapping.
            "v_swing": 1,  # Expected to map to SWING_VERTICAL.
            "econo": 0,
            "powerchill": 1,  # This should trigger preset mode PRESET_BOOST.
        }
    }

    with patch(
        "homeassistant.components.daikin_br.climate.async_send_operation_data",
        new=AsyncMock(return_value=mock_response),
    ):
        # Prepare a dummy payload (its content is not significant for the state update).
        payload = json.dumps({"port1": {"temperature": 22}})
        await climate_entity.set_thing_state(payload)

        # Verify that the public preset_mode property reflects PRESET_BOOST.
        assert climate_entity.preset_mode == PRESET_BOOST

    # Also verify that the public power_state property is updated to 1.
    assert climate_entity.power_state == 1


@pytest.mark.asyncio
async def test_set_thing_state_invalid_data_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_config_entry
) -> None:
    """Test that set_thing_state logs an error when InvalidDataException is raised."""
    # Create the DaikinClimate entity using the config entry fixture.
    # The fixture 'mock_config_entry' already sets runtime_data.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    entity.entity_id = "climate.test_device"

    # Patch async_write_ha_state to avoid actual HA state updates.
    entity.async_write_ha_state = MagicMock()

    payload = json.dumps({"port1": {"temperature": 22}})

    with patch(
        "homeassistant.components.daikin_br.climate.async_send_operation_data",
        new=AsyncMock(side_effect=InvalidDataException("Invalid Data")),
    ):
        await entity.set_thing_state(payload)

    # Verify that the error message is logged.
    # The unique_id property comes from the config entry's device_apn.
    assert f"Error executing command {entity.unique_id}:" in caplog.text
    assert "Invalid Data" in caplog.text


@pytest.mark.asyncio
async def test_handle_coordinator_update_missing_data(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that _handle_coordinator_update sets _attr_available to False.

    When the coordinator data is missing the expected 'port1' key.
    """
    # Create the DaikinClimate entity using the config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    # Patch async_write_ha_state to avoid side effects.
    entity.async_write_ha_state = MagicMock()

    # Simulate missing data by setting the dummy coordinator's data to an empty dict.
    mock_config_entry.runtime_data.data = {}

    # Call the coordinator update handler.
    entity._handle_coordinator_update()

    # Assert that the entity is marked as unavailable.
    assert entity._attr_available is False


@pytest.mark.asyncio
async def test_handle_coordinator_update_valid_calls_write_state(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that _handle_coordinator_update sets the entity as available.

    Calls update_entity_properties with valid data.
    """
    # Create the DaikinClimate entity using the config entry fixture.
    entity = DaikinClimate(mock_config_entry)
    entity.hass = hass
    entity.entity_id = "climate.test_entity"

    # Patch async_write_ha_state so we can count its calls without side effects.
    entity.async_write_ha_state = MagicMock()
    # Patch update_entity_properties so we can track its call.
    entity.update_entity_properties = MagicMock()

    # Set valid coordinator data (with "port1" present) in the runtime_data.
    mock_config_entry.runtime_data.data = {
        "port1": {"fw_ver": "1.0.0", "temperature": 24, "power": 1}
    }

    # Call the coordinator update handler.
    entity._handle_coordinator_update()

    # Verify that update_entity_properties was called with the valid data.
    entity.update_entity_properties.assert_called_once_with(
        mock_config_entry.runtime_data.data
    )
    # Verify that the entity is marked as available.
    assert entity.available is True
