"""Fixtures for the Free Mobile integration tests."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_send_sms() -> Generator[MagicMock]:
    """Mock the Free Mobile SMS client's send_sms call."""
    with patch("freesms.FreeClient.send_sms") as mock:
        mock.return_value = MagicMock(status_code=HTTPStatus.OK)
        yield mock
