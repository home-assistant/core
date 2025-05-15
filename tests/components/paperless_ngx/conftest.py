"""Common fixtures for the Paperless-ngx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.paperless_ngx.const import DOMAIN

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.paperless_ngx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="test",
        title="Paperless-ngx",
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
