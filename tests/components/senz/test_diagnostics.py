"""Tests for the diagnostics data provided by the senz integration."""

from collections.abc import Generator
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_senz_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""

    await setup_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=paths(
            "entry_data.token.expires_at",
        )
    )
