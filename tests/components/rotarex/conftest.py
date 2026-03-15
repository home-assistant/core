"""Common fixtures for the Rotarex tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.rotarex.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )


@pytest.fixture
def mock_rotarex_api() -> Generator[AsyncMock]:
    """Mock a RotarexApi client."""
    with (
        patch(
            "homeassistant.components.rotarex.coordinator.RotarexApi", autospec=True
        ) as rotarex_api,
        patch(
            "homeassistant.components.rotarex.config_flow.RotarexApi", new=rotarex_api
        ),
    ):
        api = rotarex_api.return_value
        api.login = AsyncMock(return_value=None)
        api.set_credentials = lambda *args, **kwargs: None
        api.fetch_tanks = AsyncMock(
            return_value=[
                {
                    "Guid": "tank1-guid",
                    "Name": "Tank 1",
                    "SynchDatas": [
                        {
                            "SynchDate": "2024-01-01T12:00:00Z",
                            "Level": 75.5,
                            "Battery": 85.0,
                        },
                        {
                            "SynchDate": "2024-01-02T12:00:00Z",
                            "Level": 70.0,
                            "Battery": 80.0,
                        },
                    ],
                },
                {
                    "Guid": "tank2-guid",
                    "Name": "Tank 2",
                    "SynchDatas": [
                        {
                            "SynchDate": "2024-01-01T12:00:00Z",
                            "Level": 50.0,
                            "Battery": 90.0,
                        },
                    ],
                },
            ]
        )
        yield api
