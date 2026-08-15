"""Fixtures for the Honeywell Lyric integration tests."""

from collections.abc import Generator
from time import time
from unittest.mock import MagicMock, patch

from aiolyric.objects.location import LyricLocation
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_array_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register lyric application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an already-authenticated Lyric config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time() + 3600,
                "token_type": "Bearer",
            },
        },
    )


@pytest.fixture
def mock_lyric_api() -> Generator[MagicMock]:
    """Mock the aiolyric client, backed by a real Location parsed from a live-shaped fixture.

    get_thermostat_rooms is left as an autospec'd no-op: this test only
    covers device-level sensors, not the room/priority data it would
    otherwise populate.
    """
    with patch("homeassistant.components.lyric.Lyric", autospec=True) as mock_lyric_cls:
        lyric = mock_lyric_cls.return_value

        locations_json = load_json_array_fixture("locations.json", DOMAIN)
        lyric.locations = [
            LyricLocation(MagicMock(), location) for location in locations_json
        ]
        lyric.locations_dict = {
            location.location_id: location for location in lyric.locations
        }

        yield lyric
