"""Test GitHub diagnostics."""
from collections.abc import Generator

from aiogithubapi import GitHubException
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_github_integration: Generator[None, None, None],
) -> None:
    """Test config entry diagnostics."""
    aioclient_mock.get(
        "https://api.github.com/rate_limit",
        json={"resources": {"core": {"remaining": 100, "limit": 100}}},
        headers={"Content-Type": "application/json"},
    )

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert result["options"]["repositories"] == ["home-assistant/core"]
    assert result["rate_limit"] == {
        "resources": {"core": {"remaining": 100, "limit": 100}}
    }
    assert result["repositories"]["home-assistant/core"] == {}


async def test_entry_diagnostics_exception(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_github_integration: Generator[None, None, None],
) -> None:
    """Test config entry diagnostics with exception for ratelimit."""
    aioclient_mock.get(
        "https://api.github.com/rate_limit",
        exc=GitHubException("error"),
    )

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert (
        result["rate_limit"]["error"]
        == "Unexpected exception for 'https://api.github.com/rate_limit' with - error"
    )
