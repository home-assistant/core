"""Common fixtures for the WireGuard tests."""
from collections.abc import Generator
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, patch

import pytest
import requests

from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN

from tests.common import load_fixture


def mocked_requests(*args, **kwargs):
    """Mock requests.get invocations."""

    if args[0] == "single_peer" or args[0] == DEFAULT_HOST:
        return MockResponse(
            json.loads(load_fixture("single_peer.json", DOMAIN)),
            200,
        )

    return MockResponse(None, 500)


class MockResponse(requests.Response):
    """Class to represent a mocked response."""

    def __init__(self, json_data, status_code) -> None:
        """Initialize the mock response class."""
        super().__init__()
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Return the json of the response."""
        return self.json_data

    @property
    def content(self):
        """Return the content of the response."""
        return self.json()

    def raise_for_status(self):
        """Raise an HTTPError if status is not OK."""
        if self.status_code != HTTPStatus.OK:
            raise requests.HTTPError(self.status_code)

    def close(self):
        """Close the response."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wireguard.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
