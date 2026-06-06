"""Common fixtures for the MELCloud Home tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.melcloudhome.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry

MOCK_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "thatyouevenlookedheretoseethepassword",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.melcloudhome.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_melcloud_client() -> Generator[AsyncMock]:
    """Mock MELCloud Home client context retrieval for config flow and coordinator."""
    mocked_get_context = AsyncMock(return_value=SimpleNamespace(buildings=[]))
    with (
        patch(
            "homeassistant.components.melcloudhome.config_flow.MELCloudHome.get_context",
            new=mocked_get_context,
        ),
        patch(
            "homeassistant.components.melcloudhome.coordinator.MELCloudHome.get_context",
            new=mocked_get_context,
        ),
    ):
        yield mocked_get_context


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a MELCloud Home config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_USER_INPUT[CONF_EMAIL],
        data=MOCK_USER_INPUT,
        title=MOCK_USER_INPUT[CONF_EMAIL],
    )
