"""Common fixtures for the Kiosker tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.kiosker.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.kiosker.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Kiosker Device",
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.1.5",
            CONF_PORT: 8081,
            "api_token": "test_token",
            "ssl": False,
            "ssl_verify": False,
        },
        unique_id="A98BE1CE-5FE7-4A8D-B2C3-123456789ABC",
    )


@pytest.fixture
def mock_kiosker_api():
    """Mock KioskerAPI."""
    mock_api = MagicMock()
    mock_api.host = "10.0.1.5"
    mock_api.port = 8081

    # Mock status data
    mock_status = MagicMock()
    mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
    mock_status.model = "iPad Pro"
    mock_status.os_version = "18.0"
    mock_status.app_name = "Kiosker"
    mock_status.app_version = "25.1.1"
    mock_status.battery_level = 85
    mock_status.battery_state = "charging"
    mock_status.last_interaction = "2025-01-01T12:00:00Z"
    mock_status.last_motion = "2025-01-01T11:55:00Z"
    mock_status.last_update = "2025-01-01T12:05:00Z"

    mock_api.status.return_value = mock_status

    return mock_api


@pytest.fixture
def mock_kiosker_api_class():
    """Mock the KioskerAPI class."""
    with patch(
        "homeassistant.components.kiosker.config_flow.KioskerAPI"
    ) as mock_api_class:
        yield mock_api_class
