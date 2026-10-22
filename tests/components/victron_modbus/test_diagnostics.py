"""Test Victron Modbus diagnostics."""

from modbus_connection import IllegalDataAddressError
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import set_readings


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_unit,
    snapshot: SnapshotAssertion,
) -> None:
    """The last poll and the raw registers are returned, without the serial."""
    set_readings(mock_unit)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot
    registers = result["registers"]["holding"]
    assert not any(str(address) in registers for address in range(0x1001, 0x1009))


async def test_diagnostics_read_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """A device that stops answering still yields the last poll."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_unit.fail_requests(IllegalDataAddressError())
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["polls"]["power"]["updated"] == ["power"]
    assert result["polls"]["readings"]["updated"] == ["meter", "phases"]
    assert "error" in result["registers"]
