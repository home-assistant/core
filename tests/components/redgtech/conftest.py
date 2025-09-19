"""Test fixtures for Redgtech integration."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.redgtech.const import DOMAIN

from tests.common import MockConfigEntry

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password"


@pytest.fixture
def mock_redgtech_api() -> Callable[..., AsyncMock]:
    """Mock Redgtech API."""

    def _create_mock():
        mock = Mock()
        mock.login = AsyncMock(return_value="mock_access_token")
        mock.get_data = AsyncMock(
            return_value={
                "boards": [
                    {
                        "endpointId": "switch_001",
                        "friendlyName": "Living Room Switch",
                        "value": False,
                    },
                    {
                        "endpointId": "switch_002",
                        "friendlyName": "Kitchen Switch",
                        "value": True,
                    },
                ]
            }
        )
        mock.set_switch_state = AsyncMock()
        return mock

    return _create_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        title="Mock Title",
        entry_id="test_entry",
    )
