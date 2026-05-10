"""Test fixtures for Free Mobile."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_USERNAME = "12345678"
TEST_ACCESS_TOKEN = "test_token_123"
CONF_INPUT = {CONF_USERNAME: TEST_USERNAME, CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN}


@pytest.fixture
def mock_freesms() -> Generator[MagicMock]:
    """Mock the freesms library."""
    mock_instance = MagicMock()
    mock_instance.send_sms.return_value.status_code = 200
    mock_instance.send_sms.return_value.ok = True

    with (
        patch(
            "homeassistant.components.free_mobile.config_flow.FreeClient",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.free_mobile.FreeClient",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.free_mobile.notify.FreeClient",
            return_value=mock_instance,
        ),
    ):
        yield mock_instance


@pytest.fixture
def mock_freesms_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to create a mocked ConfigEntry."""
    return MockConfigEntry(
        title=f"Free Mobile ({TEST_USERNAME})",
        domain=DOMAIN,
        data=CONF_INPUT,
    )
