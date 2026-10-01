"""Shared fixtures and helpers for FMD integration tests."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from fmd_api import FmdClient
import pytest

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.const import CONF_ID, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_URL = "https://fmd.example.com"
TEST_ID = "test_user"
TEST_PASSWORD = "test-password"

TEST_ARTIFACTS: dict[str, Any] = {
    "base_url": TEST_URL,
    "fmd_id": TEST_ID,
    "access_token": "mock_access_token",
    "private_key": "[REDACTED PRIVATE KEY]",
    "password_hash": "mock_password_hash",
    "session_duration": 3600,
    "token_issued_at": 1234567890.0,
}

TEST_LOCATION: dict[str, Any] = {
    "lat": 37.7749,
    "lon": -122.4194,
    "time": "2025-10-23T12:00:00Z",
    "date": 1761220800000,
    "provider": "gps",
    "bat": 85,
    "accuracy": 10.5,
    "altitude": 132,
    "speed": 23.42,
    "heading": 95,
}


def configure_mock_client(client: Any) -> None:
    """Configure default return values on an autospec'd FmdClient mock."""
    client.get_locations = AsyncMock(return_value=["blob1"])
    client.decrypt_data_blob = MagicMock(
        side_effect=lambda blob: json.dumps(
            blob if isinstance(blob, dict) else TEST_LOCATION
        ).encode()
    )
    client.export_auth_artifacts = AsyncMock(return_value=dict(TEST_ARTIFACTS))
    client.close = AsyncMock(return_value=None)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the FMD integration from a config entry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_URL}/{TEST_ID}",
        title=TEST_ID,
        data={
            CONF_URL: TEST_URL,
            CONF_ID: TEST_ID,
            "artifacts": dict(TEST_ARTIFACTS),
        },
    )


@pytest.fixture
def mock_fmd_client() -> Any:
    """Return a mock FmdClient with patched constructor classmethods."""
    client = create_autospec(FmdClient, instance=True)
    configure_mock_client(client)

    with (
        patch(
            "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
            return_value=client,
        ),
        patch(
            "homeassistant.components.fmd.config_flow.FmdClient.create",
            return_value=client,
        ),
    ):
        yield client
