"""Common fixtures for the canvas tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.instructure.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    MOCK_ANNOUNCEMENTS,
    MOCK_ASSIGNMENTS,
    MOCK_CONVERSATIONS,
    MOCK_GRADES,
    MOCK_QUICK_LINKS,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.instructure.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_api() -> Generator[None, MagicMock, None]:
    """Return a mock CanvasAPI object."""
    with patch("homeassistant.components.instructure.CanvasAPI", autospec=True) as mock:
        mock_instance = mock.return_value
        mock_instance.async_get_upcoming_assignments = AsyncMock(
            return_value=MOCK_ASSIGNMENTS
        )
        mock_instance.async_get_announcements = AsyncMock(
            return_value=MOCK_ANNOUNCEMENTS
        )
        mock_instance.async_get_conversations = AsyncMock(
            return_value=MOCK_CONVERSATIONS
        )
        mock_instance.async_get_grades = AsyncMock(return_value=MOCK_GRADES)
        mock_instance.get_quick_links = AsyncMock(return_value=MOCK_QUICK_LINKS)
        yield mock_instance


@pytest.fixture(name="mock_config_entry")
async def fixture_mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="0797477940f9f91760ab6051d3fb0df0",
        title="Canvas",
        data={"host_prefix": "chalmers", "access_token": "mock_access_token"},
        options={"courses": {"25271": "DAT265 / DIT588 Software evolution project"}},
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
