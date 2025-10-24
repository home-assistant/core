"""Test the Saunum select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.saunum.select import LeilSaunaSelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


async def test_select_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select entities are created."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    fan_entity_id = "select.saunum_leil_fan_speed"
    sauna_type_entity_id = "select.saunum_leil_sauna_type"

    assert entity_registry.async_get(fan_entity_id) is not None
    assert entity_registry.async_get(sauna_type_entity_id) is not None

    fan_state = hass.states.get(fan_entity_id)
    sauna_type_state = hass.states.get(sauna_type_entity_id)
    assert fan_state is not None
    assert sauna_type_state is not None


async def test_sauna_type_shows_current_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sauna type displays current device value."""
    mock_config_entry.add_to_hass(hass)

    # Coordinator with sauna_type value set to 2
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
                    2,
                    60,
                    10,
                    2,
                    1,
                    0,
                ]  # session_active=0, sauna_type=2
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    sauna_type_entity_id = "select.saunum_leil_sauna_type"
    state = hass.states.get(sauna_type_entity_id)
    # Current option should show "Sauna type 3" since device sauna_type=2 (0-indexed becomes type 3)
    assert state is not None
    assert state.state == "Sauna type 3"


async def test_select_fan_speed_option_changes_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing fan speed writes correct register value."""
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
                mock_response.registers = [0, 0, 60, 10, 2, 1, 0]  # fan_speed=1 (low)
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

        def mock_write_register(address, value, device_id=1):
            resp = MagicMock()
            resp.isError.return_value = False
            return resp

        mock_client.write_register = AsyncMock(side_effect=mock_write_register)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "select.saunum_leil_fan_speed"
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "high"},
            blocking=True,
        )

        # Fan speed register address is 5; high should map to value 3
        assert any(
            c.kwargs.get("address") == 5 and c.kwargs.get("value") == 3
            for c in mock_client.write_register.call_args_list
        )


async def test_select_sauna_type_custom_names_update_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options rebuild when config entry options change (custom names)."""
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
                    1,
                    0,
                    60,
                    10,
                    2,
                    1,
                    0,
                ]  # session active, sauna_type=0
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Simulate options update with new custom names via async_update_entry
        new_options = {
            "sauna_type_1_name": "Relax",
            "sauna_type_2_name": "Energize",
            "sauna_type_3_name": "Intense",
        }
        # async_update_entry is a synchronous callback returning bool; do not await
        hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
        await hass.async_block_till_done()

        entity_id = "select.saunum_leil_sauna_type"
        state = hass.states.get(entity_id)
        assert state is not None
        # Verify one of the new names appears in options by selecting it
        # Current selected (value 0) should now map to "Relax"
        assert state.state == "Relax"


async def test_select_fan_speed_invalid_option_no_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that selecting an invalid fan speed option results in no register writes."""
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
                mock_response.registers = [0, -1, 60, 10, 2, 1, 0]
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "select.saunum_leil_fan_speed"
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": "turbo"},  # invalid option
                blocking=True,
            )

        # Ensure no writes occurred
        assert mock_client.write_register.call_count == 0


async def test_select_sauna_type_invalid_option_no_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that selecting an invalid sauna type option results in no register writes."""
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
                mock_response.registers = [0, -1, 60, 10, 2, 1, 0]
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "select.saunum_leil_sauna_type"
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": "Extreme"},  # invalid option
                blocking=True,
            )

        # Ensure no writes occurred
        assert mock_client.write_register.call_count == 0


async def test_select_unmapped_current_option_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a custom select where current_option falls back to None (covers fallback branch)."""
    mock_config_entry.add_to_hass(hass)

    # Custom description yields a value not present in options_map
    custom_selects = (
        LeilSaunaSelectEntityDescription(
            key="fan_speed",
            translation_key="fan_speed",
            icon="mdi:fan",
            register=5,  # REG_FAN_SPEED
            options=["off"],  # limited options list
            value_fn=lambda data: 99,  # unmapped value
            options_map={0: "off"},  # mapping does not include 99
        ),
    )

    with (
        patch("homeassistant.components.saunum.select.SELECTS", custom_selects),
        patch(
            "homeassistant.components.saunum.AsyncModbusTcpClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            if address == 0:
                mock_response.registers = [0, -1, 60, 10, 2, 1, 0]
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id = "select.saunum_leil_fan_speed"
    state = hass.states.get(entity_id)
    assert state is not None
    # State should be unknown because current_option is None
    assert state.state == "unknown"


async def test_select_sauna_type_option_writes_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a sauna type writes to the register."""
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
                mock_response.registers = [0, -1, 60, 10, 2, 0, 0]
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
        mock_client.write_register = AsyncMock(
            return_value=MagicMock(isError=lambda: False)
        )

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.SELECT]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "select.saunum_leil_sauna_type"
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "Sauna type 2"},
            blocking=True,
        )

        # Should write value 1 (0-indexed) to sauna_type register (address 1)
        assert any(
            c.kwargs.get("address") == 1 and c.kwargs.get("value") == 1
            for c in mock_client.write_register.call_args_list
        )
