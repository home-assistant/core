"""Test helpers for Miele."""

from collections.abc import AsyncGenerator, Generator
import time
from unittest.mock import MagicMock, patch

from pymiele import MieleAction, MieleDevices
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from homeassistant.util.json import json_loads

from .const import CLIENT_ID, CLIENT_SECRET, UNIQUE_ID

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, expires_at: float) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        minor_version=1,
        domain=DOMAIN,
        title="Miele test",
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
        entry_id="miele_test",
        unique_id=UNIQUE_ID,
    )
    config_entry.add_to_hass(hass)
    return config_entry


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


# Fixture group for device API endpoint.


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return load_fixture("3_devices.json", DOMAIN)


@pytest.fixture
def device_fixture(load_device_file: str) -> MieleDevices:
    """Fixture for device."""
    return json_loads(load_device_file)


@pytest.fixture(scope="package")
def load_action_file() -> str:
    """Fixture for loading action file."""
    return load_fixture("action_washing_machine.json", DOMAIN)


@pytest.fixture
def action_fixture(load_action_file: str) -> MieleAction:
    """Fixture for action."""
    return json_loads(load_action_file)


@pytest.fixture
def mock_miele_client(
    device_fixture,
    action_fixture,
) -> Generator[MagicMock]:
    """Mock a Miele client."""

    with patch(
        "homeassistant.components.miele.AsyncConfigEntryAuth",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        client.get_devices.return_value = device_fixture
        client.get_actions.return_value = action_fixture

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
) -> MockConfigEntry:
    """Set up the miele integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms."""
    return []


@pytest.fixture
async def setup_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms,
) -> AsyncGenerator[None]:
    """Set up one or all platforms."""

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture
async def access_token(hass: HomeAssistant) -> str:
    """Return a valid access token."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": UNIQUE_ID,
            "aud": [],
            "scp": [],
            "ou_code": "NA",
        },
    )
