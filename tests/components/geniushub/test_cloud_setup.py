"""Test the Geniushub config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.geniushub import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def init_cloud_integration(
    hass: HomeAssistant,
) -> MockConfigEntry:
    """Set up the AccuWeather integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Genius hub",
        data={
            CONF_TOKEN: "abcdef",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(autouse=True)
def mock_cloud_all(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_array_fixture("zones_cloud_test_data.json", DOMAIN)
    devices = load_json_array_fixture("devices_cloud_test_data.json", DOMAIN)
    aioclient_mock.get(
        "https://my.geniushub.co.uk/v1/version",
        json={
            "hubSoftwareVersion": "6.3.10",
            "earliestCompatibleAPI": "my.geniushub.co.uk/v1",
            "latestCompatibleAPI": "my.geniushub.co.uk/v1",
        },
    )
    aioclient_mock.get("https://my.geniushub.co.uk/v1/zones", json=zones)
    aioclient_mock.get("https://my.geniushub.co.uk/v1/devices", json=devices)
    aioclient_mock.get("https://my.geniushub.co.uk/v1/issues", json=[])


@pytest.fixture(autouse=True)
def mock_cloud_single_zone_with_switch(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("single_zone_local_test_data.json", DOMAIN)
    devices = load_json_object_fixture("single_switch_local_test_data.json", DOMAIN)
    switch_on = load_json_object_fixture("switch_on_local_test_data.json", DOMAIN)
    switch_off = load_json_object_fixture("switch_off_local_test_data.json", DOMAIN)
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/auth/release",
        json=({"data": {"UID": "aa:bb:cc:dd:ee:ff", "release": "10.0"}}),
    )
    aioclient_mock.get("http://10.0.0.130:1223/v3/zones", json=zones)
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/data_manager",
        json=devices,
    )
    aioclient_mock.patch(
        "http://10.0.0.130:1223/v3/zone/32",
        json=switch_on,
    )
    aioclient_mock.patch(
        "http://10.0.0.131:1223/v3/zone/32",
        json=switch_off,
    )


async def test_cloud_all_sensors(
    hass: HomeAssistant,
    mock_cloud_all: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test full local flow."""
    await init_cloud_integration(hass)

    entities = [
        {
            "id": "binary_sensor.single_channel_receiver_22",
            "name": "Single Channel Receiver 22",
        },
        {"id": "sensor.geniushub_errors", "name": "GeniusHub Errors"},
        {"id": "sensor.geniushub_information", "name": "GeniusHub Information"},
        {"id": "sensor.geniushub_warnings", "name": "GeniusHub Warnings"},
        {"id": "sensor.radiator_valve_11", "name": "Radiator Valve 11"},
        {"id": "sensor.radiator_valve_56", "name": "Radiator Valve 56"},
        {"id": "sensor.radiator_valve_68", "name": "Radiator Valve 68"},
        {"id": "sensor.radiator_valve_78", "name": "Radiator Valve 78"},
        {"id": "sensor.radiator_valve_85", "name": "Radiator Valve 85"},
        {"id": "sensor.radiator_valve_88", "name": "Radiator Valve 88"},
        {"id": "sensor.radiator_valve_89", "name": "Radiator Valve 89"},
        {"id": "sensor.radiator_valve_90", "name": "Radiator Valve 90"},
        {"id": "sensor.room_sensor_16", "name": "Room Sensor 16"},
        {"id": "sensor.room_sensor_17", "name": "Room Sensor 17"},
        {"id": "sensor.room_sensor_18", "name": "Room Sensor 18"},
        {"id": "sensor.room_sensor_20", "name": "Room Sensor 20"},
        {"id": "sensor.room_sensor_21", "name": "Room Sensor 21"},
        {"id": "sensor.room_sensor_50", "name": "Room Sensor 50"},
        {"id": "sensor.room_sensor_53", "name": "Room Sensor 53"},
        {"id": "switch.bedroom_socket", "name": "Bedroom Socket"},
        {"id": "switch.kitchen_socket", "name": "Kitchen Socket"},
        {"id": "switch.study_socket", "name": "Study Socket"},
        {"id": "climate.ensuite", "name": "Ensuite"},
        {"id": "climate.bedroom", "name": "Bedroom"},
        {"id": "climate.guest_room", "name": "Guest room"},
        {"id": "climate.hall", "name": "Hall"},
        {"id": "climate.kitchen", "name": "Kitchen"},
        {"id": "climate.lounge", "name": "Lounge"},
        {"id": "climate.study", "name": "Study"},
    ]

    for entity in entities:
        state = hass.states.get(entity["id"])
        assert state.name == entity["name"]
