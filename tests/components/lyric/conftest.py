"""Fixtures for the Honeywell Lyric integration tests."""

from time import time

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

BASE_URL = "https://api.honeywellhome.com/v2"

# Real payload shapes captured from a live T9-T10 account with paired
# RCHTSENSOR room accessories. Deliberately using the actual field names
# Resideo returns (e.g. vacationHold.Enabled, accessories[].sensorType),
# not the ones aiolyric happens to read, so tests exercise real parsing
# rather than hiding behind pre-parsed mocks.
LOCATION_ID = "35202000168931"
# Deliberately "LCC-"-prefixed: this branch is intentionally cut from a
# clean base without the coordinator fix from home-assistant/core#177022
# (which removes a device-ID-prefix heuristic gating the /priority fetch).
# Using a non-"LCC-" ID here would make room-level entities fail to be
# created for that unrelated, separately-tracked reason, muddying what
# these tests are actually checking.
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

PRIORITY_RESPONSE = {
    "deviceId": MAC_ID,
    "priorityStatus": "NoHold",
    "priority": {
        "priorityType": "PickARoom",
        "selectedRooms": [1],
        "rooms": [
            {
                "id": 1,
                "name": "Primary Bedroom",
                "avgTemperature": 79,
                "avgHumidity": 54,
                "overallMotion": False,
                "accessories": [
                    {
                        "id": 1,
                        "sensorType": "IndoorAirSensor",
                        "temperature": 79,
                        "status": "Ok",
                        "detectMotion": True,
                    }
                ],
            }
        ],
    },
}


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register lyric application credentials, matching test_config_flow.py."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "cred"
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an already-authenticated Lyric config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            # Matches the credential name registered by setup_credentials via
            # async_import_client_credential(..., "cred") - confirmed against
            # test_config_flow.py's test_full_flow, which asserts a real
            # completed flow ends up with auth_implementation == "cred", not
            # DOMAIN.
            "auth_implementation": "cred",
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time() + 3600,
                "token_type": "Bearer",
            },
        },
    )


@pytest.fixture
def mock_lyric_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock the /locations and /priority HTTP endpoints with real-shaped data.

    Registered at the aiohttp transport level, so the real aiolyric client
    and coordinator code runs unmodified - only the network call itself is
    faked, using the actual field names Resideo returns.
    """
    aioclient_mock.get(
        f"{BASE_URL}/locations?apikey={CLIENT_ID}",
        json=LOCATIONS_RESPONSE,
    )
    aioclient_mock.get(
        f"{BASE_URL}/devices/thermostats/{DEVICE_ID}/priority"
        f"?apikey={CLIENT_ID}&locationId={LOCATION_ID}",
        json=PRIORITY_RESPONSE,
    )
    return aioclient_mock


async def async_setup_lyric_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the mock config entry and wait for it to settle."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
