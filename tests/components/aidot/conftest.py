"""Common fixtures for the aidot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_COUNTRY = "United States"
TEST_EMAIL = "test@gmail.com"
TEST_PASSWORD = "123456"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aidot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
    )
    config_entry.add_to_hass(hass)
    return config_entry
