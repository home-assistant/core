"""Tests for the SolarEdge Modbus diagnostics."""

from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import add_storage_capacity

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# The control blocks, each absent on a device that refuses its base address.
CONTROL_BASES = {
    "storage_control": 57348,
    "export_control": 57344,
    "power_control": 61440,
    "advanced_power_control": 61696,
}


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """The diagnostics dump matches the snapshot."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_without_control_blocks(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A block this device does not have is named in the dump, as null."""
    for address in CONTROL_BASES.values():
        mock_modbus_unit.fail_read(address, IllegalDataAddressError())

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    for name in CONTROL_BASES:
        assert diagnostics[name] is None


async def test_diagnostics_reports_the_sunspec_chain(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that serves a model chain has it in the dump.

    It is what explains a block that was looked for and not found, so it is
    worth having even where nothing was made of the models it names.
    """
    add_storage_capacity(mock_modbus_unit, state_of_charge=5960)

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert [model["model_id"] for model in diagnostics["sunspec_models"]] == [
        1,
        103,
        1,
        203,
        713,
    ]
