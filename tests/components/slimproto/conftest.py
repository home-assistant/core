"""Fixtures for the SlimProto Player integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.slimproto.const import DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Radios",
        domain=DOMAIN,
        data={},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.slimproto.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup
