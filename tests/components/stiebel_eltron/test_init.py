"""Tests for the STIEBEL ELTRON integration."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusError, ModbusTcpParams
from modbus_connection.mock import MockModbusConnection
from pystiebeleltron import StiebelEltronModbusError
import pytest

from homeassistant.components.modbus import async_get_unit
from homeassistant.components.stiebel_eltron.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    UNIT_ID,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

CLIMATE_ENTITY_ID = "climate.stiebel_eltron_lwz"


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the integration."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("entry_data", "expected_params"),
    [
        pytest.param(
            {CONF_HOST: "192.168.1.100", CONF_PORT: 5020},
            ModbusTcpParams(host="192.168.1.100", port=5020),
            id="custom_port",
        ),
        pytest.param(
            {CONF_HOST: "192.168.1.100"},
            ModbusTcpParams(host="192.168.1.100", port=502),
            id="default_port",
        ),
    ],
)
async def test_async_setup_entry_requests_unit(
    hass: HomeAssistant,
    mock_modbus_connection_class: MagicMock,
    entry_data: dict[str, Any],
    expected_params: ModbusTcpParams,
) -> None:
    """Test the unit is taken on a connection with the configured host and port."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data=entry_data,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_modbus_connection_class.assert_called_once_with(expected_params)


async def test_async_setup_entry_conflicting_link_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails with a reason when the device is held over other settings."""
    other_entry = MockConfigEntry(domain="modbus")
    other_entry.add_to_hass(hass)
    async_get_unit(
        hass,
        other_entry,
        ModbusTcpParams(host="1.1.1.1", port=502, framer="rtu"),
        UNIT_ID,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason is not None
    assert "different link settings" in mock_config_entry.reason


async def test_async_setup_entry_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup retries when the device cannot be reached or read."""
    mock_config_entry.add_to_hass(hass)
    mock_get_controller_model.side_effect = StiebelEltronModbusError()

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test setup retries and closes the connection when the first update fails."""
    mock_lwz_api.async_update.side_effect = ModbusError("update failed")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_modbus_connection.connected is False


async def test_entities_unavailable_when_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entities go unavailable when the device stops answering."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CLIMATE_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    mock_lwz_api.async_update.side_effect = ModbusError("update failed")
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CLIMATE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_unload_entry_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test unloading the config entry closes the Modbus connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_modbus_connection.connected is False


async def test_unload_entry_does_not_close_connection_if_platform_unload_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test the connection is not closed if platform unload fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_modbus_connection.connected is True
