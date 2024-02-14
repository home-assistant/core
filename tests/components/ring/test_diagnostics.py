"""Test Ring diagnostics."""

import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    requests_mock: requests_mock.Mocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Ring diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    assert diag == snapshot
