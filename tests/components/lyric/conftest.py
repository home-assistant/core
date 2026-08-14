"""Fixtures for Honeywell Lyric tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiolyric import Lyric
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricPriority, LyricRoom
import pytest

from homeassistant.components.lyric.api import LyricLocalOAuth2Implementation
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Honeywell Lyric config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_lyric() -> Generator[MagicMock]:
    """Mock an account containing a thermostat, room sensor, and leak detector."""
    client = MagicMock()
    location = LyricLocation(
        client,
        {
            "locationID": 1234,
            "name": "Home",
            "devices": [
                {
                    "deviceID": f"LCC-{MAC}",
                    "deviceClass": "Thermostat",
                    "macID": MAC,
                    "name": "Thermostat",
                    "deviceModel": "T9",
                    "units": "Fahrenheit",
                    "allowedModes": ["Heat", "Cool", "Off"],
                    "indoorTemperature": 70,
                    "changeableValues": {
                        "mode": "Heat",
                        "heatSetpoint": 68,
                        "coolSetpoint": 75,
                        "thermostatSetpointStatus": "NoHold",
                    },
                    "operationStatus": {"mode": "EquipmentOff"},
                },
                {
                    "deviceID": "leak-detector-id",
                    "deviceClass": "LeakDetector",
                    "deviceType": "Water Leak Detector",
                    "deviceVariant": "WLD3",
                    "name": "Basement Leak Detector",
                    "waterPresent": False,
                },
            ],
        },
    )
    room = LyricRoom(
        {
            "id": 1,
            "name": "Living Room",
            "avgTemperature": 71,
            "avgHumidity": 40,
            "accessories": [
                {"id": 1, "sensorType": "IndoorAirSensor", "temperature": 71}
            ],
        }
    )
    priority = LyricPriority(
        {
            "deviceId": MAC,
            "priority": {
                "priorityType": "FollowMe",
                "selectedRooms": [],
            },
        }
    )

    lyric = MagicMock(spec=Lyric)
    lyric.get_locations = AsyncMock()
    lyric.get_thermostat_rooms = AsyncMock()
    lyric.update_priority = AsyncMock()
    lyric.locations = [location]
    lyric.locations_dict = {1234: location}
    lyric.priorities_dict = {MAC: priority}
    lyric.rooms_dict = {MAC: {1: room}}

    implementation = MagicMock(spec=LyricLocalOAuth2Implementation)
    implementation.client_id = "client-id"

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=implementation,
        ),
        patch("homeassistant.components.lyric.Lyric", return_value=lyric),
    ):
        yield lyric
