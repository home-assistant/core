"""Test diagnostics for the Intergas InComfort integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry, SnapshotAssertion
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_incomfort: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the incomfort integration diagnostics."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    snapshot.assert_match(
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    )
