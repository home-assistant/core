"""conftest for the GitHub integration."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.github.const import (
    CONF_ACCESS_TOKEN,
    CONF_REPOSITORIES,
    DEFAULT_REPOSITORIES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .common import MOCK_ACCESS_TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        options={CONF_REPOSITORIES: DEFAULT_REPOSITORIES},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.github.async_setup_entry", return_value=True):
        yield


@pytest.fixture
async def setup_github_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> Generator[None, None, None]:
    """Mock setting up the integration."""
    aioclient_mock.get(
        "https://api.github.com/repos/home-assistant/core",
        json={},
        headers={"Content-Type": "application/json"},
    )
    for endpoint in ("issues", "pulls", "releases", "commits"):
        aioclient_mock.get(
            f"https://api.github.com/repos/home-assistant/core/{endpoint}",
            json=[],
            headers={"Content-Type": "application/json"},
        )
    mock_config_entry.options = {CONF_REPOSITORIES: ["home-assistant/core"]}
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
