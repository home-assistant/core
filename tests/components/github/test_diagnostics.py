"""Test GitHub diagnostics."""

import json

from aiogithubapi import GitHubException

from homeassistant.components.github.const import CONF_REPOSITORIES, DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_github_integration

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.options = {CONF_REPOSITORIES: ["home-assistant/core"]}
    response_json = json.loads(load_fixture("graphql.json", DOMAIN))
    response_json["data"]["repository"]["full_name"] = "home-assistant/core"

    aioclient_mock.post(
        "https://api.github.com/graphql",
        json=response_json,
        headers=json.loads(load_fixture("base_headers.json", DOMAIN)),
    )
    aioclient_mock.get(
        "https://api.github.com/rate_limit",
        json={"resources": {"core": {"remaining": 100, "limit": 100}}},
        headers={"Content-Type": "application/json"},
    )

    await setup_github_integration(hass, mock_config_entry, aioclient_mock)
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
    hass_client: ClientSessionGenerator,
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
