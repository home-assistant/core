"""Common fixtures for the NextDNS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nextdns.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
        entry_id="d9aa37407ddac7b964a99e86312288d6",
    )
