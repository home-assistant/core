"""Tests for the KACO RS485 diagnostics."""

from freezegun.api import FrozenDateTimeFactory
from kaco_rs485 import BusError
from kaco_rs485.testing import FakeBus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CYCLES_UNTIL_DARK, run_cycles


@pytest.mark.parametrize(
    "silenced",
    [
        pytest.param((), id="all_answering"),
        pytest.param((1,), id="one_dark"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
    snapshot: SnapshotAssertion,
    silenced: tuple[int, ...],
) -> None:
    """Test the diagnostics, including an inverter that stopped answering."""
    mock_bus.silence(*silenced)
    await run_cycles(hass, freezer, CYCLES_UNTIL_DARK)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot(exclude=props("last_polled", "last_reply_ms"))


async def test_diagnostics_before_the_first_poll(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_bus: FakeBus,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics still download while setup is retrying."""
    mock_bus.open_error = BusError("could not open /dev/ttyUSB0")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
