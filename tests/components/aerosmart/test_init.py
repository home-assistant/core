"""Tests for the aerosmart config-entry setup."""

from unittest.mock import patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_setup_entry_translates_shared_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A shared Modbus link conflict becomes a translated setup error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aerosmart.async_get_unit",
        side_effect=HomeAssistantError("incompatible shared connection"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "connect_failed"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "error": "incompatible shared connection"
    }


async def test_setup_entry_retries_after_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """A connect failure puts setup into its normal retry lifecycle."""
    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.aerosmart_outdoor_air_temperature") is None


async def test_unload_releases_shared_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Unloading lets Home Assistant release its shared connection holds."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_modbus_connection.connected is False
