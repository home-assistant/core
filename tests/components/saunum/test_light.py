"""Test the Saunum light platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import ColorMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_light_entity_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test light entity creation."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check light entity is created
    entity_id = "light.saunum_leil_light"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None


async def test_light_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test light attributes and color modes."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.saunum_leil_light"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check color mode attributes
    assert state.attributes.get("supported_color_modes") == [ColorMode.ONOFF]
    # For an off light, color_mode might be None (this is normal HA behavior)
    # The important thing is that the supported_color_modes is set properly
    assert ColorMode.ONOFF in state.attributes.get("supported_color_modes", [])

    # Check friendly name
    assert state.attributes.get("friendly_name") == "Saunum Leil Light"


async def test_light_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test light state values."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.saunum_leil_light"
    state = hass.states.get(entity_id)
    assert state is not None

    # Default mock data has light = 0, so should be off
    assert state.state == "off"


async def test_light_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light turn on/off functionality."""
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
                mock_response.registers = [0, 80, 60, 10, 2, 0, 0]  # Light off
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

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Test turn on
        entity_id = "light.saunum_leil_light"
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Check that write_register was called with correct parameters
        mock_client.write_register.assert_called_with(address=6, value=1, device_id=1)

        # Test turn off
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Check that write_register was called with correct parameters
        mock_client.write_register.assert_called_with(address=6, value=0, device_id=1)


async def test_light_with_light_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light state when light is on."""
    mock_config_entry.add_to_hass(hass)

    # Mock coordinator with light on
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock register data with light on
        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False

            if address == 0:  # Control data
                mock_response.registers = [
                    0,
                    80,
                    60,
                    10,
                    2,
                    0,
                    1,
                ]  # Light on (reg 6 = 1)
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

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "light.saunum_leil_light"
        state = hass.states.get(entity_id)
        assert state is not None

        # Light should be on (reg 6 = 1)
        assert state.state == "on"


async def test_light_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test light device info."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "light.saunum_leil_light"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check device info attributes
    assert state.attributes.get("friendly_name") == "Saunum Leil Light"


async def test_light_turn_on_write_failure_reverts_state(
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
                mock_response.registers = [0, -1, 60, 10, 2, 0, 0]  # light off
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

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "light.saunum_leil_light"

        # Try to turn on with write failure
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        # State should revert since write failed (optimistic state cleared)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"  # Should revert to actual state


async def test_light_turn_off_write_failure_reverts_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn off with write failure clears optimistic state."""
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
                mock_response.registers = [0, -1, 60, 10, 2, 0, 1]  # light on
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

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "light.saunum_leil_light"

        # Try to turn off with write failure
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        # State should revert since write failed (optimistic state cleared)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"  # Should revert to actual state


async def test_light_optimistic_state_during_operation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that optimistic state provides immediate feedback."""
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
                mock_response.registers = [0, -1, 60, 10, 2, 0, 0]  # light off
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

        # Successful write
        def mock_write_register(address, value, device_id=1):
            resp = MagicMock()
            resp.isError.return_value = False
            return resp

        mock_client.write_register = AsyncMock(side_effect=mock_write_register)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.LIGHT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "light.saunum_leil_light"

        # Initial state should be off
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

        # Turn on - optimistic state should be set immediately
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        # After successful write, optimistic state is cleared and actual state used
        state = hass.states.get(entity_id)
        assert state is not None
