"""Test GitHub diagnostics."""

from unittest.mock import AsyncMock

from aiogithubapi import GitHubException
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert result == snapshot


async def test_entry_diagnostics_exception(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test config entry diagnostics with exception for ratelimit."""
    await setup_integration(hass, mock_config_entry)
    github_client.rate_limit.side_effect = GitHubException("error")

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert result["rate_limit"]["error"] == "error"
