"""Provide common fixtures for the YoLink integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from yolink.home_manager import YoLinkHome

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "12345"
CLIENT_SECRET = "6789"
DOMAIN = "yolink"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="mock_auth_mgr")
def mock_auth_mgr():
    """Mock the authentication manager."""
    return MagicMock()


@pytest.fixture(name="mock_yolink_home")
def mock_yolink_home():
    """Mock YoLink home instance."""
    return AsyncMock(spec=YoLinkHome)
