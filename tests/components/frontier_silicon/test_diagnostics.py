"""Tests for the diagnostics data provided by the Frontier Silicon integration."""

from unittest.mock import AsyncMock

from afsapi import FSNotImplementedError, PlayCaps
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, config_entry)
    mock_afsapi.get_play_caps.return_value = PlayCaps.PAUSE | PlayCaps.SKIP_NEXT
    mock_afsapi.get_dst.side_effect = FSNotImplementedError

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
