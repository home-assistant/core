"""Tests for the diagnostics data provided by the Spotify integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("setup_credentials")
async def test_diagnostics_polling_instance(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_spotify: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("position_updated_at"))
