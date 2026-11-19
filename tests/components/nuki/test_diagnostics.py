"""Test the Nuki diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_nuki_requests: requests_mock.Mocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = await init_integration(hass, mock_nuki_requests)
    assert entry.state is ConfigEntryState.LOADED

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot

    # Unload while the requests are mocked, as removing the webhook on stop
    # calls the bridge
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
