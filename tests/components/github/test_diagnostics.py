"""Test GitHub diagnostics."""

from unittest.mock import AsyncMock

from aiogithubapi import GitHubException

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert result["options"]["repositories"] == ["octocat/Hello-World"]
    assert result["rate_limit"] == {
        "resources": {"core": {"remaining": 100, "limit": 100}}
    }
    assert (
        result["repositories"]["octocat/Hello-World"]["full_name"]
        == "octocat/Hello-World"
    )


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
