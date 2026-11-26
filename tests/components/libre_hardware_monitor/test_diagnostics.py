"""Tests for Libre Hardware Monitor diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_auth_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await init_integration(hass, mock_auth_config_entry)
    assert (
        await get_diagnostics_for_config_entry(
            hass, hass_client, mock_auth_config_entry
        )
        == snapshot
    )
