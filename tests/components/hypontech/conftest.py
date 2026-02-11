"""Common fixtures for the Hypontech Cloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hypontech.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_hyponcloud() -> Generator[AsyncMock]:
    """Mock HyponCloud."""
    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_overview",
        ) as mock_get_overview,
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_list",
        ) as mock_get_list,
    ):
        mock_get_overview.return_value = AsyncMock()
        mock_get_list.return_value = []
        yield mock_get_overview
