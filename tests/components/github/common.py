"""Common helpers for GitHub integration tests."""
from __future__ import annotations

import json

from homeassistant import config_entries
from homeassistant.components.github.const import CONF_REPOSITORIES, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ACCESS_TOKEN = "gho_16C7e42F292c6912E7710c838347Ae178B4a"
TEST_REPOSITORY = "octocat/Hello-World"


async def setup_github_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Mock setting up the integration."""
    headers = json.loads(load_fixture("base_headers.json", DOMAIN))
    for idx, repository in enumerate(mock_config_entry.options[CONF_REPOSITORIES]):
        aioclient_mock.get(
            f"https://api.github.com/repos/{repository}",
            json={
                **json.loads(load_fixture("repository.json", DOMAIN)),
                "full_name": repository,
                "id": idx,
            },
            headers=headers,
        )
        aioclient_mock.get(
            f"https://api.github.com/repos/{repository}/events",
            json=[],
            headers=headers,
        )
    aioclient_mock.post(
        "https://api.github.com/graphql",
        json=json.loads(load_fixture("graphql.json", DOMAIN)),
        headers=headers,
    )
    mock_config_entry.add_to_hass(hass)

    setup_result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_result
    assert mock_config_entry.state == config_entries.ConfigEntryState.LOADED
