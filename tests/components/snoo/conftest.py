"""Common fixtures for the Happiest Baby Snoo tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_snoo.containers import SnooDevice

from .const import MOCK_SNOO_DEVICES, MOCKED_AUTH


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snoo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="bypass_api")
def bypass_api() -> Generator[AsyncMock]:
    """Bypass the Snoo api."""
    with (
        patch("homeassistant.components.snoo.Snoo", autospec=True) as mock_client,
        patch("homeassistant.components.snoo.config_flow.Snoo", new=mock_client),
    ):
        client = mock_client.return_value
        client.get_devices.return_value = [SnooDevice.from_dict(MOCK_SNOO_DEVICES[0])]
        client.authorize.return_value = MOCKED_AUTH
        yield client
