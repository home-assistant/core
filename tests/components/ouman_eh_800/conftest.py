"""Common fixtures for the Ouman EH-800 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ouman_eh_800.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_URL = "http://192.168.1.100"
TEST_USERNAME = "test-user"
TEST_PASSWORD = "test-pass"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ouman_eh_800.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ouman EH-800",
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id="abcdef0123456789abcdef0123456789",
    )


@pytest.fixture
def mock_ouman_client() -> Generator[AsyncMock]:
    """Mock the Ouman EH-800 client."""
    client = AsyncMock()
    client.get_active_registries.return_value = MagicMock(endpoints=[])
    client.get_values.return_value = {}
    with (
        patch(
            "homeassistant.components.ouman_eh_800.coordinator.OumanEh800Client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.ouman_eh_800.config_flow.OumanEh800Client",
            return_value=client,
        ),
    ):
        yield client
