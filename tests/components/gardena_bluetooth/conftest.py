"""Common fixtures for the Gardena Bluetooth tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from gardena_bluetooth.client import Client
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gardena_bluetooth.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_client(enable_bluetooth):
    """Auto mock bluetooth."""

    client = Mock(spec_set=Client)
    client.get_all_characteristics_uuid.return_value = set()

    with patch(
        "homeassistant.components.gardena_bluetooth.config_flow.Client",
        return_value=client,
    ):
        yield client
