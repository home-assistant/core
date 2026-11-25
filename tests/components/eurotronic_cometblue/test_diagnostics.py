"""Tests for the diagnostics data provided by the Eurotronic Comet Blue integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import setup_with_selected_platforms


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a config entry."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "time")
    )
