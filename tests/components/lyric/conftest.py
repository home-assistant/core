"""Fixtures for the Honeywell Lyric integration tests."""

from collections.abc import Generator
from time import time
from unittest.mock import patch

from aiolyric import Lyric
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

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

BASE_URL = "https://api.honeywellhome.com/v2"

# Real payload shape captured from a live account, using the actual field
# names Resideo returns (e.g. vacationHold.Enabled) rather than the ones
# aiolyric happens to read, so the test exercises real parsing instead of
# a pre-parsed mock.
LOCATION_ID = "35202000168931"
# Use an LCC-prefixed ID so the current coordinator fetches room data.
DEVICE_ID = "LCC-7f86b153-8480-f111-b78f-6045bdb25006"
MAC_ID = "5CFCE1B67035"

LOCATIONS_RESPONSE = [
    {
        "locationID": LOCATION_ID,
        "name": "Ocala P01",
        "devices": [
            {
                "vacationHold": {"Enabled": True},
                "scheduleStatus": "Resume",
                "settings": {"devicePairingEnabled": True},
                "deviceClass": "Thermostat",
                "deviceType": "Thermostat",
                "deviceID": DEVICE_ID,
                "name": "Ocala",
                "macID": MAC_ID,
                "units": "Fahrenheit",
                "indoorTemperature": 79,
                "deviceModel": "T9-T10",
            }
        ],
        "users": [],
    }
]


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
def mock_lyric_api() -> Generator[None]:
    """Patch the aiolyric client to build a real Location object.

    Patches Lyric.get_locations directly rather than mocking HTTP
    responses, so the test exercises real aiolyric parsing (the same
    LyricLocation code reading the actual field names Resideo returns)
    without depending on network-mocking machinery. get_thermostat_rooms
    is a no-op: this test only covers device-level sensors, not the
    room/priority data it would otherwise populate.
    """

    async def get_locations(self: Lyric) -> None:
        self._locations = [
            LyricLocation(self._client, location) for location in LOCATIONS_RESPONSE
        ]
        self._locations_dict = {
            location.location_id: location for location in self._locations
        }

    async def get_thermostat_rooms(
        self: Lyric, location_id: str, device_id: str
    ) -> None:
        return

    with (
        patch.object(Lyric, "get_locations", get_locations),
        patch.object(Lyric, "get_thermostat_rooms", get_thermostat_rooms),
    ):
        yield


async def async_setup_lyric_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the mock config entry and wait for it to settle."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
