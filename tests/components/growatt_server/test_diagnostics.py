"""Tests for the diagnostics data provided by the Growatt Server integration."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_growatt_v1_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics for V1 API (token auth) config entry."""
    await setup_integration(hass, mock_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id"))


async def test_diagnostics_classic_api(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
) -> None:
    """Test diagnostics for Classic API (password auth) config entry."""
    await setup_integration(hass, mock_config_entry_classic)

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry_classic,
    )
    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
    # Verify credentials are redacted
    assert result["config_entry"]["data"]["password"] == "**REDACTED**"
    assert result["config_entry"]["data"]["username"] == "**REDACTED**"
