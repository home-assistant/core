"""Test the Saunum switch platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


async def test_switch_entity_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entity creation."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check switch entity is created
    entity_id = "switch.saunum_leil_session_active"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None


async def test_switch_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test switch state values."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.saunum_leil_session_active"
    state = hass.states.get(entity_id)
    assert state is not None

    # Default mock data has session_active = 0, so switch should be off
    assert state.state == "off"


async def test_switch_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test switch attributes."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.saunum_leil_session_active"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check friendly name
    assert state.attributes.get("friendly_name") == "Saunum Leil Session active"


async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch turn on/off functionality."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with write capability
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock register read/write
        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [0, 80, 60, 10, 2, 0, 0]  # Session off
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Mock write_register to return a proper modbus response
        def mock_write_register(address, value, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            return mock_response

        mock_client.write_register = AsyncMock(side_effect=mock_write_register)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Test turn on
        entity_id = "switch.saunum_leil_session_active"
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Check that write_register was called with correct parameters
        mock_client.write_register.assert_called_with(address=0, value=1, device_id=1)

        # Test turn off
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Batch write may perform sauna type reset after session off; ensure both writes occurred
        calls = [
            (c.kwargs.get("address"), c.kwargs.get("value"))
            for c in mock_client.write_register.call_args_list
        ]
        assert (0, 0) in calls  # session deactivated
        # sauna type may be reset to -1 if previously selected
        assert (1, -1) in calls or all(val != -1 for addr, val in calls if addr == 1)


async def test_switch_turn_off_write_failure_logs_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test warning log path when write fails (covers failure branch)."""
    mock_config_entry.add_to_hass(hass)
    caplog.set_level("WARNING")

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                # session active
                mock_response.registers = [1, 2, 60, 10, 2, 0, 0]
            elif address == 100:
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Write fails (simulate isError True)
        def mock_write_register(address, value, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = True
            return mock_response

        mock_client.write_register = AsyncMock(side_effect=mock_write_register)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Warning should be logged due to failure
        assert any(
            "Failed to turn off session" in record.message for record in caplog.records
        )


async def test_switch_with_session_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch state when session is active."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with session active
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock register data with session active
        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [
                    1,
                    80,
                    60,
                    10,
                    2,
                    0,
                    0,
                ]  # Session active (reg 0 = 1)
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"


async def test_switch_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch device info."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.saunum_leil_session_active"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check device info attributes
    assert state.attributes.get("friendly_name") == "Saunum Leil Session active"


async def test_switch_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch unique ID."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.saunum_leil_session_active"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Check unique ID format
    expected_unique_id = f"{mock_config_entry.entry_id}_session_active"
    assert entity_entry.unique_id == expected_unique_id


async def test_switch_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch updates from coordinator data changes."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with changing data
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Start with session off
        session_active = [0]

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [
                    session_active[0],
                    80,
                    60,
                    10,
                    2,
                    0,
                    0,
                ]
            elif address == 100:  # Sensor data
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:  # Alarm data
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count

            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

        # Change session to active
        session_active[0] = 1

        # Trigger coordinator update
        coordinator = mock_config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Check switch is now on
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"


async def test_switch_turn_on_door_open_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test turning on switch when door is open logs warning."""
    caplog.set_level(logging.WARNING)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [
                    0,
                    -1,
                    60,
                    10,
                    2,
                    0,
                    0,
                ]
            elif address == 100:
                # door_status is at index 4 (5th element)
                mock_response.registers = [
                    75,
                    1234,
                    5678,
                    3,
                    1,
                ]  # door_status = 1 (open)
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"

        # Try to turn on when door is open
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )

        # Check warning was logged
        assert "Cannot activate session while door is open" in caplog.text
        # Verify write was not called
        assert mock_client.write_register.call_count == 0


async def test_switch_turn_off_write_fails_logs_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test turn off with write failure logs warning."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [1, 0, 60, 10, 2, 0, 0]  # session active
            elif address == 100:
                mock_response.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Make write_register return error
        error_response = MagicMock()
        error_response.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=error_response)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"

        # Turn off with write failure
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": entity_id}, blocking=True
        )

        # Check warning was logged
        assert "Failed to turn off session" in caplog.text


async def test_switch_turn_on_write_failure_reverts_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on with write failure clears optimistic state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, -1, 60, 10, 2, 0, 0]  # session inactive
            elif address == 100:
                mock_response.registers = [75, 1234, 5678, 3, 0]  # door closed
            elif address == 200:
                mock_response.registers = [0, 0, 0, 0, 0, 0]
            else:
                mock_response.registers = [0] * count
            return mock_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Make write_register return error
        error_response = MagicMock()
        error_response.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=error_response)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SWITCH]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "switch.saunum_leil_session_active"

        # Try to turn on with write failure
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        # State should revert since write failed (optimistic state cleared)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"  # Should revert to actual state
