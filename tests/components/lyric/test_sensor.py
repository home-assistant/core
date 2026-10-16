"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiolyric import Lyric
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lyric.api import LyricLocalOAuth2Implementation
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

_MAC = "AABBCCDDEEFF"


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


@pytest.mark.usefixtures("setup_credentials", "mock_lyric_mixed_devices")
async def test_room_sensors_created_regardless_of_device_id_prefix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Room/accessory sensors are created regardless of device ID prefix."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    lcc_room_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000001_room0_acc0_room_temperature"
        )
    )
    assert lcc_room_sensor.state == "22.5"

    non_lcc_room_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000002_room0_acc0_room_temperature"
        )
    )
    assert non_lcc_room_sensor.state == "24.5"

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000003_room0_acc0_room_temperature"
        )
        is None
    )

    unsupported_device_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000003_indoor_temperature"
        )
    )
    assert unsupported_device_sensor.state == "21.5"


@pytest.mark.usefixtures("setup_credentials", "mock_lyric_api")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lyric sensor platform via a real config entry setup."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def _mock_lyric() -> MagicMock:
    """Build a fake aiolyric Lyric client with one thermostat and one room accessory."""
    client = MagicMock()
    location = LyricLocation(
        client,
        {
            "locationID": 1234,
            "name": "Home",
            "devices": [
                # A thermostat with no device-level sensors: the sensor platform
                # creates no thermostat entity, so the thermostat device can only
                # come from the up-front registration in async_setup_entry.
                {
                    "deviceID": f"LCC-{_MAC}",
                    "deviceClass": "Thermostat",
                    "macID": _MAC,
                    "name": "Thermostat",
                    "deviceModel": "T5-T6",
                }
            ],
        },
    )
    room = LyricRoom(
        {
            "id": 1,
            "name": "Living Room",
            "avgTemperature": 21,
            "avgHumidity": 40,
            "accessories": [
                {"id": 1, "sensorType": "IndoorAirSensor", "temperature": 21}
            ],
        }
    )

    lyric = MagicMock(spec=Lyric)
    lyric.get_locations = AsyncMock()
    lyric.get_thermostat_rooms = AsyncMock()
    lyric.locations = [location]
    lyric.locations_dict = {1234: location}
    lyric.rooms_dict = {_MAC: {1: room}}
    return lyric


async def test_accessory_links_to_thermostat_via_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test room accessory devices resolve the thermostat as their via_device."""
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

    implementation = MagicMock(spec=LyricLocalOAuth2Implementation)
    implementation.client_id = "client-id"

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=implementation,
        ),
        patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]),
        patch("homeassistant.components.lyric.Lyric", return_value=_mock_lyric()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    thermostat = device_registry.async_get_device_by_identifier(
        (dr.CONNECTION_NETWORK_MAC, _MAC), entry.entry_id
    )
    assert thermostat is not None

    accessory = device_registry.async_get_device_by_identifier(
        (f"{dr.CONNECTION_NETWORK_MAC}_room_accessory", f"{_MAC}_room1_accessory1"),
        entry.entry_id,
    )
    assert accessory is not None
    assert accessory.via_device_id == thermostat.id
