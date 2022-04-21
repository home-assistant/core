"""esphome session fixtures."""

from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_connector() -> Generator:
    """Mock API connector."""
    with patch("homeassistant.components.moonraker.APIConnector") as mock_client:

        def mock_constructor(host, port, ssl, session=None):
            """Fake the client constructor."""
            mock_client.host = host
            mock_client.port = port
            mock_client.ssl = ssl
            mock_client.session = session
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.start = AsyncMock(return_value=True)
        mock_client.stop = AsyncMock()
        mock_client.client = MagicMock()
        mock_client.client.call_method = AsyncMock()

        yield mock_client
