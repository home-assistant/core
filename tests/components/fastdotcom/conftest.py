"""Common fixtures for the Fast.com tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER

from . import MOCK_DATA


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        source=SOURCE_USER,
        data={},
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )


@pytest.fixture
def mock_async_fast_com() -> Generator[AsyncMock]:
    """Mock async_fast_com."""
    with patch(
        "homeassistant.components.fastdotcom.coordinator.async_fast_com",
        new_callable=AsyncMock,
        return_value=MOCK_DATA,
    ) as mock_client:
        yield mock_client
