"""Fixtures for Hanna Instruments integration tests."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hanna.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.hanna.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_hanna_client():
    """Mock HannaCloudClient."""
    with patch(
        "homeassistant.components.hanna.config_flow.HannaCloudClient"
    ) as mock_client:
        client = mock_client.return_value
        client.authenticate = (
            MagicMock()
        )  # Use MagicMock since it's called synchronously
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test-password"},
        title="test@example.com",
    )
