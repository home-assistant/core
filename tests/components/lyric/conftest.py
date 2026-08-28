"""Fixtures for the Honeywell Lyric integration tests."""

from collections.abc import AsyncGenerator, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiolyric import Lyric
from aiolyric.exceptions import LyricException
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricPriority, LyricRoom
import pytest

from homeassistant.components.application_credentials import (
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
    """Set up the application credentials required for the Lyric OAuth2 flow."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), DOMAIN
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Lyric config entry with a valid OAuth2 token."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time.time() + 3600,
                "token_type": "Bearer",
            },
        },
    )


def thermostat_json(
    mac_id: str, device_id: str, name: str = "Thermostat"
) -> dict[str, Any]:
    """Return a raw aiolyric device payload for a single thermostat."""
    return {
        **load_json_object_fixture("thermostat.json", DOMAIN),
        "deviceID": device_id,
        "macID": mac_id,
        "name": name,
    }


def location_json(location_id: int, devices: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a raw aiolyric location payload containing the given devices."""
    return {"locationID": location_id, "name": "Home", "devices": devices}


def build_mock_lyric(
    locations: list[LyricLocation], rooms_dict: dict | None = None
) -> MagicMock:
    """Build a mocked aiolyric client backed by real aiolyric location/device objects."""
    lyric = MagicMock(spec=Lyric)
    lyric.locations = locations
    lyric.locations_dict = {location.location_id: location for location in locations}
    lyric.rooms_dict = rooms_dict or {}
    return lyric


def lyric_exception(
    status: int, code: str | None = "GetPriorityFailed"
) -> LyricException:
    """Build a LyricException matching aiolyric's actual payload shape."""
    return LyricException(
        {
            "request": {"method": "GET", "url": "https://example.com"},
            "response": {"code": code} if code else {},
            "status": status,
        }
    )


LCC_SUPPORTED_MAC = "AABBCC000001"
NON_LCC_SUPPORTED_MAC = "AABBCC000002"
UNSUPPORTED_MAC = "AABBCC000003"
UNSUPPORTED_DEVICE_ID = "LCC-AABBCC000003"

LIVING_ROOM_JSON = {
    "id": 0,
    "name": "Living Room",
    "avgTemperature": 22,
    "avgHumidity": 50,
    "accessories": [
        {"id": 0, "sensorType": "IndoorAirSensor", "temperature": 22.5, "status": "Ok"}
    ],
}

OFFICE_ROOM_JSON = {
    "id": 0,
    "name": "Office",
    "avgTemperature": 24,
    "avgHumidity": 40,
    "accessories": [
        {"id": 0, "sensorType": "IndoorAirSensor", "temperature": 24.5, "status": "Ok"}
    ],
}


@pytest.fixture
async def mock_lyric_mixed_devices() -> AsyncGenerator[MagicMock]:
    """Yield a mocked Lyric client with an LCC device, a non-LCC device, and an unsupported device."""
    location = LyricLocation(
        MagicMock(),
        location_json(
            1,
            [
                thermostat_json(LCC_SUPPORTED_MAC, "LCC-AABBCC000001", "Living Room"),
                thermostat_json(NON_LCC_SUPPORTED_MAC, "TCC-AABBCC000002", "Office"),
                thermostat_json(UNSUPPORTED_MAC, UNSUPPORTED_DEVICE_ID, "Bedroom"),
            ],
        ),
    )
    rooms = {
        LCC_SUPPORTED_MAC: LIVING_ROOM_JSON,
        NON_LCC_SUPPORTED_MAC: OFFICE_ROOM_JSON,
    }
    mac_by_device_id = {device.device_id: device.mac_id for device in location.devices}

    lyric = MagicMock(spec=Lyric)
    lyric.locations = [location]
    lyric.locations_dict = {location.location_id: location}
    lyric.rooms_dict = {}
    lyric.priorities_dict = {}

    async def get_thermostat_rooms(location_id: int, device_id: str) -> None:
        if device_id == UNSUPPORTED_DEVICE_ID:
            raise lyric_exception(400)
        mac_id = mac_by_device_id[device_id]
        room_json = rooms[mac_id]
        lyric.rooms_dict[mac_id] = {room_json["id"]: LyricRoom(room_json)}

    lyric.get_thermostat_rooms = AsyncMock(side_effect=get_thermostat_rooms)

    with patch("homeassistant.components.lyric.Lyric", return_value=lyric):
        yield lyric


@pytest.fixture
def mock_lyric_api() -> Generator[MagicMock]:
    """Mock the aiolyric client, backed by a real Location and a real LyricPriority."""
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
