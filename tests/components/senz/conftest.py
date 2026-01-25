"""Fixtures for Senz testing."""

from collections.abc import Generator
import time
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from pysenz import Account, Thermostat
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.senz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET, ENTRY_UNIQUE_ID

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return "thermostats.json"


@pytest.fixture
async def device_fixture(
    hass: HomeAssistant, load_device_file: str
) -> list[dict[str, Any]]:
    """Fixture for device."""
    return await async_load_json_array_fixture(hass, load_device_file, DOMAIN)


@pytest.fixture(scope="package")
def load_account_file() -> str:
    """Fixture for loading account file."""
    return "account.json"


@pytest.fixture
async def account_fixture(
    hass: HomeAssistant, load_account_file: str
) -> dict[str, Any]:
    """Fixture for device."""
    return await async_load_json_object_fixture(hass, load_account_file, DOMAIN)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, expires_at: float) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        minor_version=2,
        domain=DOMAIN,
        title="Senz test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "Fake_token",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="senz_test",
        unique_id=ENTRY_UNIQUE_ID,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_senz_client(account_fixture, device_fixture) -> Generator[MagicMock]:
    """Mock thermostat data."""
    with patch("homeassistant.components.senz.SENZAPI", autospec=True) as mock_senz:
        client = mock_senz.return_value

        client.get_account.return_value = Account(account_fixture)
        client.get_thermostats.return_value = [
            Thermostat(device, Mock()) for device in device_fixture
        ]

        yield client


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        DOMAIN,
    )


@pytest.fixture
def unique_id() -> str:
    """Return a unique ID."""
    return ENTRY_UNIQUE_ID


@pytest.fixture
async def access_token(hass: HomeAssistant, unique_id: str) -> str:
    """Return a valid access token."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": unique_id,
            "aud": [],
            "scp": [
                "rest_api",
                "offline_access",
            ],
            "ou_code": "NA",
        },
    )
