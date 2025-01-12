"""Fixtures for Azure Storage tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.azure_storage.const import DOMAIN

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.azure_storage.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the Azure Storage client."""
    with (
        patch(
            "homeassistant.components.azure_storage.config_flow.ContainerClient",
            autospec=True,
        ) as container_client,
        patch(
            "homeassistant.components.azure_storage.ContainerClient",
            new=container_client,
        ),
    ):
        client = container_client.return_value
        client.exists.return_value = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        data=USER_INPUT,
    )
