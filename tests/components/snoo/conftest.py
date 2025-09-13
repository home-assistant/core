"""Common fixtures for the Happiest Baby Snoo tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from python_snoo.containers import SnooDevice

from .const import MOCK_BABY_DATA, MOCK_SNOO_DEVICES, MOCKED_AUTH


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

        # Mock the tokens attribute that the Baby class needs
        mock_tokens = MagicMock()
        mock_tokens.aws_id = "mock_aws_id"
        client.tokens = mock_tokens

        # Mock the session attribute with proper async get method
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=MOCK_BABY_DATA.to_dict())
        mock_session.get = AsyncMock(return_value=mock_response)
        client.session = mock_session

        # Mock the get_status method to avoid actual API calls
        client.get_status = AsyncMock()

        # Mock the start_subscribe method
        client.start_subscribe = MagicMock()

        # Mock the generate_snoo_auth_headers method
        client.generate_snoo_auth_headers = MagicMock(return_value={})

        yield client
