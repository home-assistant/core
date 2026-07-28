"""Karakeep tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.karakeep.const import DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

from .const import TEST_STATS, TEST_TOKEN, TEST_URL, TEST_VERSION

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.karakeep.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_karakeep_client() -> Generator[AsyncMock]:
    """Mock a Karakeep client."""
    with (
        patch(
            "homeassistant.components.karakeep.KarakeepClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.karakeep.config_flow.KarakeepClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_stats.return_value = TEST_STATS
        client.async_get_version.return_value = TEST_VERSION
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Karakeep",
        data={
            CONF_URL: TEST_URL,
            CONF_TOKEN: TEST_TOKEN,
            CONF_VERIFY_SSL: True,
        },
        entry_id="01KVCW3ET6GZ025S7ARE8D5M8W",
    )
