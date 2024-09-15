"""Fixtures for ezbeq tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import ezbeq
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ezbeq.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_ezbeq_client() -> Generator[AsyncMock]:
    """Mock an ezbeq client."""
    with patch(
        "homeassistant.components.ezbeq.EzbeqClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.host = MOCK_CONFIG[CONF_HOST]
        client.port = MOCK_CONFIG[CONF_PORT]
        client.server_url = f"http://{MOCK_CONFIG[CONF_HOST]}:{MOCK_CONFIG[CONF_PORT]}"
        client.current_profile = "Test Profile"
        client.current_media_type = "Movie"
        client.version = "1.0.0"
        client.device_info = []
        client.client = AsyncMock()
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=ezbeq.const.DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_CONFIG[CONF_HOST],
        title="EzBEQ",
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the ezbeq integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
