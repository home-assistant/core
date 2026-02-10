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
        api.login.return_value = None
        api.fetch_tanks.return_value = [
            {"id": "tank1", "name": "Tank 1"},
            {"id": "tank2", "name": "Tank 2"},
        ]
        yield api
