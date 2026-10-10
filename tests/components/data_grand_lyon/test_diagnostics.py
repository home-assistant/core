"""Tests for the Data Grand Lyon diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    "entry_fixture",
    [
        pytest.param("mock_config_entry", id="stops"),
        pytest.param("mock_velov_config_entry", id="velov"),
        pytest.param("mock_park_and_ride_config_entry", id="park_and_ride"),
        pytest.param("mock_line_config_entry", id="line"),
    ],
)
@pytest.mark.usefixtures("mock_tcl_client")
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics for every kind of subentry."""
    config_entry: MockConfigEntry = request.getfixturevalue(entry_fixture)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id", "subentry_id"))
