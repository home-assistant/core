"""Test the Tractive diagnostics."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    await init_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(exclude=props("created_at", "modified_at"))
