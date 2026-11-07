"""Test the Victron Modbus integration setup."""

from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import OTHER_SERIAL, P1LINK, SERIAL, VM_3P75CT, set_identity


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_unit
) -> None:
    """The entry sets up, refreshes once and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_update_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_unit
) -> None:
    """A Modbus error on the first refresh maps to a setup retry."""
    mock_unit.fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_nothing_could_be_read(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_unit
) -> None:
    """A poll in which every sub-system failed is an update failure."""
    mock_unit.fail_read(0x3034, IllegalDataAddressError())
    mock_unit.fail_read(0x3040, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("product_id", "serial"),
    [(VM_3P75CT, OTHER_SERIAL), (P1LINK, SERIAL), (0xA389, SERIAL)],
    ids=["other_serial", "other_model", "unknown_product"],
)
async def test_setup_refuses_another_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit,
    product_id: int,
    serial: str,
) -> None:
    """Another device at the entry's address is not set up as this one."""
    set_identity(mock_unit, product_id, serial=serial)
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
