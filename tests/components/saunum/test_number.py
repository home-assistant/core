"""Tests for the Saunum number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


async def _setup_number_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    holding_registers: list[int],
) -> MagicMock:
    """Helper to set up number platform with provided holding registers."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Provide three register blocks: control (0), sensor (100), alarm (200)
        control_regs = holding_registers
        sensor_regs = [75, 1234, 5678, 3, 0]
        alarm_regs = [0, 0, 0, 0, 0, 0]

        def mock_read_holding_registers(address, count, device_id=1):
            resp = MagicMock()
            resp.isError.return_value = False
            if address == 0:
                resp.registers = control_regs
            elif address == 100:
                resp.registers = sensor_regs
            elif address == 200:
                resp.registers = alarm_regs
            else:
                resp.registers = [0] * count
            return resp

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        def mock_write_register(address, value, device_id=1):
            resp = MagicMock()
            resp.isError.return_value = False
            return resp

        mock_client.write_register = AsyncMock(side_effect=mock_write_register)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.NUMBER]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        return mock_client


async def test_number_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number entities are created."""
    # control_regs: session_active, target_temp, sauna_duration, fan_duration, ..., ensure lengths
    mock_client = await _setup_number_platform(
        hass,
        mock_config_entry,
        [0, 80, 60, 10, 2, 0, 0],
    )

    # Entities: target_temperature, sauna_duration, fan_duration
    assert hass.states.get("number.saunum_leil_target_temperature") is not None
    assert hass.states.get("number.saunum_leil_sauna_duration") is not None
    assert hass.states.get("number.saunum_leil_fan_duration") is not None

    # Ensure no writes yet
    assert mock_client.write_register.call_count == 0


async def test_set_target_temperature_converts_and_writes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting target temperature writes Celsius value after conversion."""
    mock_client = await _setup_number_platform(
        hass,
        mock_config_entry,
        [0, 90, 60, 10, 2, 0, 0],  # initial target temp 90C
    )

    entity_id = "number.saunum_leil_target_temperature"
    # Set a new temperature; we assume system unit is same (Celsius) so direct write
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 95},
        blocking=True,
    )

    # Register for target temperature is REG_TARGET_TEMPERATURE (4) in coordinator mapping
    # Ensure the value written matches integer conversion
    assert any(
        c.kwargs.get("address") == 4 and c.kwargs.get("value") == 95
        for c in mock_client.write_register.call_args_list
    )

    # Try a float value (should be cast to int before write)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 96.7},
        blocking=True,
    )
    assert any(
        c.kwargs.get("address") == 4 and c.kwargs.get("value") == 96
        for c in mock_client.write_register.call_args_list
    )


async def test_set_duration_blocked_when_session_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sauna_duration change is blocked when session_active == 1."""
    mock_client = await _setup_number_platform(
        hass,
        mock_config_entry,
        [1, 80, 60, 10, 2, 0, 0],  # session_active=1
    )

    entity_id = "number.saunum_leil_sauna_duration"
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 75},
        blocking=True,
    )

    # Should not write because session is active
    assert not any(
        c.kwargs.get("address") == 2 for c in mock_client.write_register.call_args_list
    )


async def test_set_fan_duration_blocked_when_session_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fan_duration change is blocked when session_active == 1."""
    mock_client = await _setup_number_platform(
        hass,
        mock_config_entry,
        [1, 80, 60, 10, 2, 0, 0],  # session_active=1
    )

    entity_id = "number.saunum_leil_fan_duration"
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 20},
        blocking=True,
    )

    # Should not write because session is active
    assert not any(
        c.kwargs.get("address") == 3 for c in mock_client.write_register.call_args_list
    )


async def test_set_durations_when_session_inactive_writes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duration changes write when session is inactive."""
    mock_client = await _setup_number_platform(
        hass,
        mock_config_entry,
        [0, 80, 60, 10, 2, 0, 0],  # session_active=0
    )

    sauna_duration_id = "number.saunum_leil_sauna_duration"
    fan_duration_id = "number.saunum_leil_fan_duration"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": sauna_duration_id, "value": 65},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": fan_duration_id, "value": 15},
        blocking=True,
    )

    assert any(
        c.kwargs.get("address") == 2 and c.kwargs.get("value") == 65
        for c in mock_client.write_register.call_args_list
    )
    assert any(
        c.kwargs.get("address") == 3 and c.kwargs.get("value") == 15
        for c in mock_client.write_register.call_args_list
    )


async def test_write_failure_logs_and_does_not_raise(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a write failure logs an error and continues."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        def mock_read_holding_registers(address, count, device_id=1):
            resp = MagicMock()
            resp.isError.return_value = False
            if address == 0:
                resp.registers = [0, 80, 60, 10, 2, 0, 0]
            elif address == 100:
                resp.registers = [75, 1234, 5678, 3, 0]
            elif address == 200:
                resp.registers = [0, 0, 0, 0, 0, 0]
            else:
                resp.registers = [0] * count
            return resp

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )

        # Failure response for write
        failure_resp = MagicMock()
        failure_resp.isError.return_value = True
        mock_client.write_register = AsyncMock(return_value=failure_resp)

        with patch("homeassistant.components.saunum.PLATFORMS", [Platform.NUMBER]):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        entity_id = "number.saunum_leil_fan_duration"
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": 25},
            blocking=True,
        )

        # Error should be logged
        assert any("Error writing register" in rec.message for rec in caplog.records)
