"""Test configuration and mocks for the google sheets integration."""

from collections.abc import Awaitable, Callable, Generator
import time

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_sheets.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_SHEET_ID = "google-sheet-id"

ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SHEET_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
    )


@pytest.fixture(name="config_entry_with_options")
def mock_config_entry_with_options(
    expires_at: int, scopes: list[str]
) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SHEET_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        options={"sheets_access": "read_only"},
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Generator[ComponentSetup, None, None]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("client-id", "client-secret"),
        DOMAIN,
    )

    async def func() -> None:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return func
