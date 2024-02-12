"""Test helpers for myuplink."""
from collections.abc import Generator
import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

from myuplink import Device, System
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="myUplink test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "Fake_token",
                "scope": "READSYSTEM offline",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="myuplink_test",
    )


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
def mock_myuplink_client() -> Generator[MagicMock, None, None]:
    """Mock a myuplink client."""

    def process_json_system(data: dict[str, Any]) -> System:
        array = json.loads(data)
        return [System(system_data) for system_data in array["systems"]]

    with patch(
        "homeassistant.components.myuplink.MyUplinkAPI",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_device_points_json.return_value = load_json_value_fixture(
            "device_points_nibe_f730.json", DOMAIN
        )
        client.async_get_systems.return_value = process_json_system(
            load_fixture("systems.json", DOMAIN)
        )
        client.async_get_device.return_value = Device(
            load_json_value_fixture("device.json", DOMAIN)
        )
        client.async_get_device_json.return_value = load_json_value_fixture(
            "device.json", DOMAIN
        )
        client.async_get_systems_json.return_value = load_json_value_fixture(
            "systems.json", DOMAIN
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_myuplink_client: MagicMock,
) -> MockConfigEntry:
    """Set up the myuplink integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
