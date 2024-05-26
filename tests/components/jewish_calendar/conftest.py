"""Common fixtures for the jewish_calendar tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.jewish_calendar import const

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=const.DEFAULT_NAME,
        domain=const.DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.jewish_calendar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
