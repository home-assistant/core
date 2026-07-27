"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom
import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import build_mock_lyric, location_json, lyric_exception, thermostat_json

from tests.common import MockConfigEntry


def test_get_datetime_from_future_time_none() -> None:
    """Test that None input returns None instead of raising."""
    assert get_datetime_from_future_time(None) is None


def test_get_datetime_from_future_time_invalid() -> None:
    """Test that an unparsable time string returns None."""
    assert get_datetime_from_future_time("not_a_time") is None


def test_get_datetime_from_future_time_valid() -> None:
    """Test that a valid time string returns a datetime."""
    result = get_datetime_from_future_time("13:30:00")
    assert isinstance(result, datetime)


ROOM_JSON = {
    "id": 0,
    "roomName": "Hallway",
    "roomAvgTemp": 22,
    "roomAvgHumidity": 50,
    "accessories": [
        {
            "id": 0,
            "type": "IndoorAirSensor",
            "temperature": 22.5,
            "status": "Ok",
        }
    ],
}


@pytest.mark.usefixtures("setup_credentials")
async def test_room_sensors_skip_device_without_priority_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device that doesn't support room priority data shouldn't block setup or other devices' sensors."""
    location = LyricLocation(
        MagicMock(),
        location_json(
            1,
            [
                thermostat_json("AABBCC000001", "LCC-AABBCC000001", "Living Room"),
                thermostat_json("AABBCC000002", "LCC-AABBCC000002", "Bedroom"),
            ],
        ),
    )
    lyric = build_mock_lyric(
        [location], rooms_dict={"AABBCC000001": {0: LyricRoom(ROOM_JSON)}}
    )

    async def get_thermostat_rooms(location_id: int, device_id: str) -> None:
        if device_id == "LCC-AABBCC000002":
            raise lyric_exception(400)

    lyric.get_thermostat_rooms.side_effect = get_thermostat_rooms

    with (
        patch("homeassistant.components.lyric.Lyric", return_value=lyric),
        patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    living_room_temperature = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000001_indoor_temperature"
        )
    )
    assert living_room_temperature.state == "21.5"

    bedroom_temperature = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000002_indoor_temperature"
        )
    )
    assert bedroom_temperature.state == "21.5"

    room_sensor_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "AABBCC000001_room0_acc0_room_temperature"
    )
    assert hass.states.get(room_sensor_entity_id).state == "22.5"

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000002_room0_acc0_room_temperature"
        )
        is None
    )
