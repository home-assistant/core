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

# Matches the values baked into fixtures/locations.json.
LOCATION_ID = "35202000168931"
DEVICE_ID = "LCC-7f86b153-8480-f111-b78f-6045bdb25006"
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
    """Mock the aiolyric client, backed by a real Location and directly-set priority data.

    Patches Lyric where the integration imports it (autospec, like the
    mealie client mock). Location/device data comes from a real
    LyricLocation parsed from a live-shaped fixture, so field-name
    parsing is still exercised for real.

    rooms_dict/priorities_dict are set directly with lightweight stand-ins
    rather than real LyricPriority objects: LyricPriority.status/
    current_priority currently read the wrong JSON keys (tracked upstream
    in aiolyric#165), and that parsing bug belongs to aiolyric's own test
    suite, not this integration's. This fixture tests that Home
    Assistant's own gating/display logic is correct once priority data
    exists, independent of whether the currently-pinned aiolyric can
    actually produce it.

    The fixture's second device has room data but no priority entry, so
    both branches of LyricPriorityStatusSensor.native_value get exercised
    through real entity state rather than a direct unit test.
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

        lyric.priorities_dict = {MAC_ID: MagicMock(status="NoHold")}
        lyric.rooms_dict = {
            MAC_ID: {1: MagicMock()},
            NO_PRIORITY_DATA_MAC_ID: {1: MagicMock()},
        }

        yield lyric
