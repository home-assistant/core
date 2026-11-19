"""Fixtures for the Untappd integration tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from aiountappd import Checkin, User
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.untappd.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"
ACCESS_TOKEN = "mock-access-token"
USER_ID = 1234567


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.untappd.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_untappd_client() -> Generator[AsyncMock]:
    """Mock the Untappd client."""
    with (
        patch(
            "homeassistant.components.untappd.UntappdClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.untappd.config_flow.UntappdClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.get_user_info.return_value = User.from_dict(
            load_json_object_fixture("user_info.json", DOMAIN)["response"]["user"]
        )
        client.get_user_checkins.return_value = [
            Checkin.from_dict(item)
            for item in load_json_object_fixture("user_checkins.json", DOMAIN)[
                "response"
            ]["checkins"]["items"]
        ][:1]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an Untappd config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="hopsfan",
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "expires_in": 315360000,
                "expires_at": time.time() + 315360000,
            },
        },
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), DOMAIN
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
