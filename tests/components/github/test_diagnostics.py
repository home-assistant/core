"""Test GitHub diagnostics."""

from aiogithubapi import GitHubException
from aiohttp import ClientSession

from homeassistant.components.github.const import CONF_REPOSITORIES
from homeassistant.core import HomeAssistant

from .common import setup_github_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.options = {CONF_REPOSITORIES: ["home-assistant/core"]}
    await setup_github_integration(hass, mock_config_entry, aioclient_mock)
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
    assert (
        result["repositories"]["home-assistant/core"]["full_name"]
        == "home-assistant/core"
    )


async def test_entry_diagnostics_exception(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config entry diagnostics with exception for ratelimit."""
    aioclient_mock.get(
        "https://api.github.com/rate_limit",
        exc=GitHubException("error"),
    )

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        init_integration,
    )

    assert (
        result["rate_limit"]["error"]
        == "Unexpected exception for 'https://api.github.com/rate_limit' with - error"
    )
