"""conftest for the GitHub integration."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.github.const import (
    CONF_ACCESS_TOKEN,
    CONF_REPOSITORIES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .common import MOCK_ACCESS_TOKEN, TEST_REPOSITORY, setup_github_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        options={CONF_REPOSITORIES: [TEST_REPOSITORY]},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.github.async_setup_entry", return_value=True):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> MockConfigEntry:
    """Set up the GitHub integration for testing."""
    await setup_github_integration(hass, mock_config_entry, aioclient_mock)
    return mock_config_entry
