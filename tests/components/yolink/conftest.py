"""Provide common fixtures for the YoLink integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yolink.home_manager import YoLinkHome

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.yolink.api import ConfigEntryAuth
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

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


@pytest.fixture(name="mock_auth_manager")
def mock_auth_manager() -> Generator[MagicMock]:
    """Mock the authentication manager."""
    with patch(
        "homeassistant.components.yolink.api.ConfigEntryAuth", autospec=True
    ) as mock_auth:
        mock_auth.return_value = MagicMock(spec=ConfigEntryAuth)
        yield mock_auth


@pytest.fixture(name="mock_yolink_home")
def mock_yolink_home() -> Generator[AsyncMock]:
    """Mock YoLink home instance."""
    with patch(
        "homeassistant.components.yolink.YoLinkHome", autospec=True
    ) as mock_home:
        mock_home.return_value = AsyncMock(spec=YoLinkHome)
        yield mock_home


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry for YoLink."""
    config_entry = MockConfigEntry(
        unique_id=DOMAIN,
        domain=DOMAIN,
        title="yolink",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "scope": "create",
            },
        },
        options={},
    )
    config_entry.add_to_hass(hass)
    return config_entry
