"""Fixtures for the Honeywell Lyric integration tests."""

import time
from typing import Any
from unittest.mock import MagicMock

from aiolyric import Lyric
from aiolyric.exceptions import LyricException
from aiolyric.objects.location import LyricLocation
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


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
        "deviceClass": "Thermostat",
        "deviceID": device_id,
        "macID": mac_id,
        "name": name,
        "units": "Celsius",
        "indoorTemperature": 21.5,
        "indoorHumidity": 45,
        "outdoorTemperature": 10,
        "displayedOutdoorHumidity": 60,
        "deviceModel": "T9",
        "changeableValues": {
            "mode": "Heat",
            "heatSetpoint": 20,
            "coolSetpoint": 24,
            "thermostatSetpointStatus": "NoHold",
        },
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
