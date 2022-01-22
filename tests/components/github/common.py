"""Common helpers for GitHub integration tests."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.github.const import CONF_REPOSITORIES
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ACCESS_TOKEN = "gho_16C7e42F292c6912E7710c838347Ae178B4a"


async def setup_github_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Mock setting up the integration."""
    repository_id = 1
    for repository in mock_config_entry.options[CONF_REPOSITORIES]:
        aioclient_mock.get(
            f"https://api.github.com/repos/{repository}",
            json={"full_name": repository, "id": repository_id},
            headers={"Content-Type": "application/json"},
        )
        repository_id += 1
        for endpoint in ("issues", "pulls", "releases", "commits"):
            aioclient_mock.get(
                f"https://api.github.com/repos/{repository}/{endpoint}",
                json=[],
                headers={"Content-Type": "application/json"},
            )
    mock_config_entry.add_to_hass(hass)

    setup_result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_result
    assert mock_config_entry.state == config_entries.ConfigEntryState.LOADED
