"""Unit tests for the Todoist integration."""
from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.todoist.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_platforms() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.todoist.PLATFORMS", return_value=[]
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_load_unload(
    hass: HomeAssistant,
    setup_integration: None,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test loading and unloading of the config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert todoist_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(todoist_config_entry.entry_id)
    assert todoist_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("todoist_api_status", [HTTPStatus.INTERNAL_SERVER_ERROR])
async def test_init_failure(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test an initialization error on integration load."""
    assert todoist_config_entry.state == ConfigEntryState.SETUP_RETRY
