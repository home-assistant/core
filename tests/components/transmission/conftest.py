"""Conftest for transmission integration."""

from unittest.mock import patch

import pytest
from transmissionrpc.session import Session

from . import SESSION_FIELDS


@pytest.fixture(autouse=True)
def mock_api():
    """Mock transmission client."""
    with patch("transmissionrpc.Client") as mock_client:
        mock_client.return_value._request.return_value = {}
        mock_client.return_value.get_session.return_value = Session(
            fields=SESSION_FIELDS
        )
        yield mock_client
