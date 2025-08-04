"""Fixtures for the TuneBlade Remote integration tests."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_tuneblade_api():
    """Fixture to mock the TuneBlade API client."""

    with patch(
        "homeassistant.components.tuneblade_remote.TuneBladeApiClient"
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_get_data = AsyncMock(
            return_value={
                "abc": {
                    "id": "abc",
                    "name": "Device ABC",
                    "connected": True,
                    "volume": 75,
                    "status_code": "1",
                },
                "master": {
                    "id": "master",
                    "name": "Master Output",
                    "connected": True,
                    "volume": 100,
                    "status_code": "1",
                },
            }
        )
        yield instance
