"""Test the Saunum binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor entity creation."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check all binary sensor entities are created
    expected_entities = [
        "binary_sensor.saunum_leil_door",
        "binary_sensor.saunum_leil_alarm_door_open",
        "binary_sensor.saunum_leil_alarm_door_sensor",
        "binary_sensor.saunum_leil_alarm_thermal_cutoff",
        "binary_sensor.saunum_leil_alarm_internal_temperature",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_shorted",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_not_connected",
    ]

    for entity_id in expected_entities:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None


async def test_binary_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test binary sensor state values."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Default mock data has no alarms (all 0s), so all alarm sensors should be off
    alarm_entities = [
        "binary_sensor.saunum_leil_alarm_door_open",
        "binary_sensor.saunum_leil_alarm_door_sensor",
        "binary_sensor.saunum_leil_alarm_thermal_cutoff",
        "binary_sensor.saunum_leil_alarm_internal_temperature",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_shorted",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_not_connected",
    ]

    for entity_id in alarm_entities:
        state = hass.states.get(entity_id)
        assert state.state == "off"

    # Door status should be off (0 in mock data)
    door_state = hass.states.get("binary_sensor.saunum_leil_door")
    assert door_state.state == "off"


async def test_binary_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test binary sensor attributes."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check door sensor device class
    door_state = hass.states.get("binary_sensor.saunum_leil_door")
    assert door_state.attributes.get("device_class") == "door"

    # Check alarm sensor device classes (should all be "problem")
    alarm_entities = [
        "binary_sensor.saunum_leil_alarm_door_open",
        "binary_sensor.saunum_leil_alarm_door_sensor",
        "binary_sensor.saunum_leil_alarm_thermal_cutoff",
        "binary_sensor.saunum_leil_alarm_internal_temperature",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_shorted",
        "binary_sensor.saunum_leil_alarm_temperature_sensor_not_connected",
    ]

    for entity_id in alarm_entities:
        state = hass.states.get(entity_id)
        assert state.attributes.get("device_class") == "problem"


async def test_binary_sensor_with_alarms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states when alarms are active."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with alarm data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock alarm registers with some alarms active
        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 80, 60, 10, 2, 0, 0]  # Control settings
            elif address == 100:  # Sensor data
                mock_response.registers = [
                    75,
                    1234,
                    5678,
                    3,
                    1,
                ]  # Door open (sensor_regs[4] = 1)
            elif address == 200:  # Alarm data - set some alarms
                mock_response.registers = [1, 1, 0, 1, 0, 0]  # Some alarms active
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch(
            "homeassistant.components.saunum.PLATFORMS", [Platform.BINARY_SENSOR]
        ):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Check door status is now on (1 in mock data)
        door_state = hass.states.get("binary_sensor.saunum_leil_door")
        assert door_state.state == "on"

        # Check specific alarm states
        alarm_door_open = hass.states.get("binary_sensor.saunum_leil_alarm_door_open")
        assert alarm_door_open.state == "on"

        alarm_door_sensor = hass.states.get(
            "binary_sensor.saunum_leil_alarm_door_sensor"
        )
        assert alarm_door_sensor.state == "on"

        alarm_thermal = hass.states.get(
            "binary_sensor.saunum_leil_alarm_thermal_cutoff"
        )
        assert alarm_thermal.state == "off"  # Index 2 = 0

        alarm_internal = hass.states.get(
            "binary_sensor.saunum_leil_alarm_internal_temperature"
        )
        assert alarm_internal.state == "on"  # Index 3 = 1


async def test_binary_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor device info."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "binary_sensor.saunum_leil_door"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check device info attributes
    assert state.attributes.get("friendly_name") == "Saunum Leil Door"
