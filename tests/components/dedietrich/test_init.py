"""Test the De Dietrich setup."""

from unittest.mock import patch

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.dedietrich.const import DEFAULT_UNIT_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_retry_when_identity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup is retried when the boiler identity cannot be read."""
    mock_connection.for_unit(DEFAULT_UNIT_ID).fail_read(457, ModbusTimeoutError("boom"))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dedietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
