"""Test the Nibe Heat Pump setup."""

from unittest.mock import Mock

from nibe.exceptions import AddressInUseException, ModbusUrlException
from nibe.heatpump import Model
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nibe_heatpump import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, MockConnection


async def test_listening_port_in_use(
    hass: HomeAssistant, mock_connection: MockConnection
) -> None:
    """Test that setup is retried when the NibeGW listening port is in use."""
    mock_connection.start.side_effect = AddressInUseException("in use")
    entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_ENTRY_DATA, "model": Model.F1155.name}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "address_in_use"


async def test_invalid_modbus_url(
    hass: HomeAssistant, mock_connection_construct: Mock
) -> None:
    """Test that setup fails for good when the Modbus URL isn't supported."""
    mock_connection_construct.side_effect = ModbusUrlException("bad url")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "model": Model.S320.name,
            "modbus_url": "bad://url",
            "modbus_unit": 0,
            "connection_type": "modbus",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "modbus_url_invalid"
