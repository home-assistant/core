"""Fixtures for aladdin_connect tests."""

import pytest

from homeassistant.components.aladdin_connect import DOMAIN
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET, USER_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Define a mock config entry fixture."""
    return MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Aladdin Connect",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-token",
                "refresh_token": "old-refresh-token",
                "expires_in": 3600,
                "expires_at": 1234567890,
            },
        },
        source="user",
        unique_id=USER_ID,
    )
