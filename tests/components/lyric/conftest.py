"""Fixtures for the Honeywell Lyric integration tests."""

from collections.abc import Generator
from time import time
from unittest.mock import MagicMock, patch

from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricPriority
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

MAC_ID = "5CFCE1B67035"
# Second device: has room data but no priority data yet, exercising the
# defensive "no priority entry" branch of LyricPriorityStatusSensor.
NO_PRIORITY_DATA_MAC_ID = "5CFCE1B67036"


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
    """Mock the aiolyric client, backed by a real Location and a real LyricPriority.

    priorities_dict holds a real LyricPriority parsed from priority.json,
    exercising the same priorityStatus key aiolyric's own
    get_thermostat_rooms() parses production responses into. rooms_dict
    only needs to be a truthy per-device gate for LyricPriorityStatusSensor
    creation, so it stays a MagicMock placeholder. The second device has
    room data but no priority entry, exercising both branches of
    LyricPriorityStatusSensor.native_value.
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

        priority_json = load_json_object_fixture("priority.json", DOMAIN)
        lyric.priorities_dict = {MAC_ID: LyricPriority(priority_json)}
        lyric.rooms_dict = {
            MAC_ID: {1: MagicMock()},
            NO_PRIORITY_DATA_MAC_ID: {1: MagicMock()},
        }

        yield lyric
