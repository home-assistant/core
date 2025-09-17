"""Test Mastodon diagnostics."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonNotFoundError
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_entry_diagnostics_fallback_to_instance_v1(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics with fallback to instance_v1 when instance_v2 raises MastodonNotFoundError."""
    mock_mastodon_client.instance_v2.side_effect = MastodonNotFoundError(
        "Instance v2 not found"
    )

    await setup_integration(hass, mock_config_entry)

    diagnostics_result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    mock_mastodon_client.instance_v1.assert_called()

    assert diagnostics_result == snapshot
