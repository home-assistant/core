"""Test fixtures for Redgtech integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.redgtech.const import DOMAIN

from tests.common import MockConfigEntry

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password"


@pytest.fixture
def mock_redgtech_api() -> Generator[MagicMock]:
    """Return a mocked Redgtech API client."""
    with (
        patch(
            "homeassistant.components.redgtech.coordinator.RedgtechAPI", autospec=True
        ) as api_mock,
        patch(
            "homeassistant.components.redgtech.config_flow.RedgtechAPI",
            new=api_mock,
        ),
    ):
        api = api_mock.return_value

        api.login = AsyncMock(return_value="mock_access_token")
        api.get_data = AsyncMock(
            return_value={
                "boards": [
                    {
                        "endpointId": "switch_001",
                        "friendlyName": "Living Room Switch",
                        "value": False,
                        "displayCategories": ["SWITCH"],
                    },
                    {
                        "endpointId": "switch_002",
                        "friendlyName": "Kitchen Switch",
                        "value": True,
                        "displayCategories": ["SWITCH"],
                    },
                    {
                        "endpointId": "light_switch_001",
                        "friendlyName": "Bedroom Light Switch",
                        "value": False,
                        "displayCategories": ["LIGHT", "SWITCH"],
                    },
                ]
            }
        )
        api.set_switch_state = AsyncMock()

        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        title="Mock Title",
        entry_id="test_entry",
    )
