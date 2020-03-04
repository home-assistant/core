"""Philips Hue sensors platform tests."""
import asyncio
from collections import deque
import logging
from unittest.mock import Mock

import aiohue
from aiohue.sensors import Sensors
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import sensor_base as hue_sensor_base

_LOGGER = logging.getLogger(__name__)

PRESENCE_SENSOR_1_PRESENT = {
    "state": {"presence": True, "lastupdated": "2019-01-01T01:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T00:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "sensitivity": 2,
        "sensitivitymax": 2,
        "pending": [],
    },
    "name": "Living room sensor",
    "type": "ZLLPresence",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue motion sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:77-02-0406",
    "capabilities": {"certified": True},
}
LIGHT_LEVEL_SENSOR_1 = {
    "state": {
        "lightlevel": 1,
        "dark": True,
        "daylight": True,
        "lastupdated": "2019-01-01T01:00:00",
    },
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T00:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "tholddark": 12467,
        "tholdoffset": 7000,
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue ambient light sensor 1",
    "type": "ZLLLightLevel",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue ambient light sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:77-02-0400",
    "capabilities": {"certified": True},
}
TEMPERATURE_SENSOR_1 = {
    "state": {"temperature": 1775, "lastupdated": "2019-01-01T01:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T01:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue temperature sensor 1",
    "type": "ZLLTemperature",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue temperature sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:77-02-0402",
    "capabilities": {"certified": True},
}
PRESENCE_SENSOR_2_NOT_PRESENT = {
    "state": {"presence": False, "lastupdated": "2019-01-01T00:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T01:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "sensitivity": 2,
        "sensitivitymax": 2,
        "pending": [],
    },
    "name": "Kitchen sensor",
    "type": "ZLLPresence",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue motion sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:88-02-0406",
    "capabilities": {"certified": True},
}
LIGHT_LEVEL_SENSOR_2 = {
    "state": {
        "lightlevel": 10001,
        "dark": True,
        "daylight": True,
        "lastupdated": "2019-01-01T01:00:00",
    },
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T00:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "tholddark": 12467,
        "tholdoffset": 7000,
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue ambient light sensor 2",
    "type": "ZLLLightLevel",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue ambient light sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:88-02-0400",
    "capabilities": {"certified": True},
}
TEMPERATURE_SENSOR_2 = {
    "state": {"temperature": 1875, "lastupdated": "2019-01-01T01:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T01:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue temperature sensor 2",
    "type": "ZLLTemperature",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue temperature sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:88-02-0402",
    "capabilities": {"certified": True},
}
PRESENCE_SENSOR_3_PRESENT = {
    "state": {"presence": True, "lastupdated": "2019-01-01T01:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T00:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "sensitivity": 2,
        "sensitivitymax": 2,
        "pending": [],
    },
    "name": "Bedroom sensor",
    "type": "ZLLPresence",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue motion sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:99-02-0406",
    "capabilities": {"certified": True},
}
LIGHT_LEVEL_SENSOR_3 = {
    "state": {
        "lightlevel": 1,
        "dark": True,
        "daylight": True,
        "lastupdated": "2019-01-01T01:00:00",
    },
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T00:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "tholddark": 12467,
        "tholdoffset": 7000,
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue ambient light sensor 3",
    "type": "ZLLLightLevel",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue ambient light sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:99-02-0400",
    "capabilities": {"certified": True},
}
TEMPERATURE_SENSOR_3 = {
    "state": {"temperature": 1775, "lastupdated": "2019-01-01T01:00:00"},
    "swupdate": {"state": "noupdates", "lastinstall": "2019-01-01T01:00:00"},
    "config": {
        "on": True,
        "battery": 100,
        "reachable": True,
        "alert": "none",
        "ledindication": False,
        "usertest": False,
        "pending": [],
    },
    "name": "Hue temperature sensor 3",
    "type": "ZLLTemperature",
    "modelid": "SML001",
    "manufacturername": "Philips",
    "productname": "Hue temperature sensor",
    "swversion": "6.1.1.27575",
    "uniqueid": "00:11:22:33:44:55:66:99-02-0402",
    "capabilities": {"certified": True},
}
UNSUPPORTED_SENSOR = {
    "state": {"status": 0, "lastupdated": "2019-01-01T01:00:00"},
    "config": {"on": True, "reachable": True},
    "name": "Unsupported sensor",
    "type": "CLIPGenericStatus",
    "modelid": "PHWA01",
    "manufacturername": "Philips",
    "swversion": "1.0",
    "uniqueid": "arbitrary",
    "recycle": True,
}
SENSOR_RESPONSE = {
    "1": PRESENCE_SENSOR_1_PRESENT,
    "2": LIGHT_LEVEL_SENSOR_1,
    "3": TEMPERATURE_SENSOR_1,
    "4": PRESENCE_SENSOR_2_NOT_PRESENT,
    "5": LIGHT_LEVEL_SENSOR_2,
    "6": TEMPERATURE_SENSOR_2,
}


def create_mock_bridge(hass):
    """Create a mock Hue bridge."""
    bridge = Mock(
        hass=hass,
        available=True,
        authorized=True,
        allow_unreachable=False,
        allow_groups=False,
        api=Mock(),
        reset_jobs=[],
        spec=hue.HueBridge,
    )
    bridge.sensor_manager = hue_sensor_base.SensorManager(bridge)
    bridge.mock_requests = []
    # We're using a deque so we can schedule multiple responses
    # and also means that `popleft()` will blow up if we get more updates
    # than expected.
    bridge.mock_sensor_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        bridge.mock_requests.append(kwargs)

        if path == "sensors":
            return bridge.mock_sensor_responses.popleft()
        return None

    async def async_request_call(task):
        await task()

    bridge.async_request_call = async_request_call
    bridge.api.config.apiversion = "9.9.9"
    bridge.api.sensors = Sensors({}, mock_request)
    return bridge


@pytest.fixture
def mock_bridge(hass):
    """Mock a Hue bridge."""
    return create_mock_bridge(hass)


async def setup_bridge(hass, mock_bridge, hostname=None):
    """Load the Hue platform with the provided bridge."""
    if hostname is None:
        hostname = "mock-host"
    hass.config.components.add(hue.DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": hostname},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
    )
    mock_bridge.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge}
    await hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    # and make sure it completes before going further
    await hass.async_block_till_done()


async def test_no_sensors(hass, mock_bridge):
    """Test the update_items function when no sensors are found."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_sensor_responses.append({})
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 0


async def test_sensors_with_multiple_bridges(hass, mock_bridge):
    """Test the update_items function with some sensors."""
    mock_bridge_2 = create_mock_bridge(hass)
    mock_bridge_2.mock_sensor_responses.append(
        {
            "1": PRESENCE_SENSOR_3_PRESENT,
            "2": LIGHT_LEVEL_SENSOR_3,
            "3": TEMPERATURE_SENSOR_3,
        }
    )
    mock_bridge.mock_sensor_responses.append(SENSOR_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    await setup_bridge(hass, mock_bridge_2, hostname="mock-bridge-2")

    assert len(mock_bridge.mock_requests) == 1
    assert len(mock_bridge_2.mock_requests) == 1
    # 3 "physical" sensors with 3 virtual sensors each
    assert len(hass.states.async_all()) == 9


async def test_sensors(hass, mock_bridge):
    """Test the update_items function with some sensors."""
    mock_bridge.mock_sensor_responses.append(SENSOR_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    # 2 "physical" sensors with 3 virtual sensors each
    assert len(hass.states.async_all()) == 6

    presence_sensor_1 = hass.states.get("binary_sensor.living_room_sensor_motion")
    light_level_sensor_1 = hass.states.get("sensor.living_room_sensor_light_level")
    temperature_sensor_1 = hass.states.get("sensor.living_room_sensor_temperature")
    assert presence_sensor_1 is not None
    assert presence_sensor_1.state == "on"
    assert light_level_sensor_1 is not None
    assert light_level_sensor_1.state == "1.0"
    assert light_level_sensor_1.name == "Living room sensor light level"
    assert temperature_sensor_1 is not None
    assert temperature_sensor_1.state == "17.75"
    assert temperature_sensor_1.name == "Living room sensor temperature"

    presence_sensor_2 = hass.states.get("binary_sensor.kitchen_sensor_motion")
    light_level_sensor_2 = hass.states.get("sensor.kitchen_sensor_light_level")
    temperature_sensor_2 = hass.states.get("sensor.kitchen_sensor_temperature")
    assert presence_sensor_2 is not None
    assert presence_sensor_2.state == "off"
    assert light_level_sensor_2 is not None
    assert light_level_sensor_2.state == "10.0"
    assert light_level_sensor_2.name == "Kitchen sensor light level"
    assert temperature_sensor_2 is not None
    assert temperature_sensor_2.state == "18.75"
    assert temperature_sensor_2.name == "Kitchen sensor temperature"


async def test_unsupported_sensors(hass, mock_bridge):
    """Test that unsupported sensors don't get added and don't fail."""
    response_with_unsupported = dict(SENSOR_RESPONSE)
    response_with_unsupported["7"] = UNSUPPORTED_SENSOR
    mock_bridge.mock_sensor_responses.append(response_with_unsupported)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    # 2 "physical" sensors with 3 virtual sensors each
    assert len(hass.states.async_all()) == 6


async def test_new_sensor_discovered(hass, mock_bridge):
    """Test if 2nd update has a new sensor."""
    mock_bridge.mock_sensor_responses.append(SENSOR_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 6

    new_sensor_response = dict(SENSOR_RESPONSE)
    new_sensor_response.update(
        {
            "7": PRESENCE_SENSOR_3_PRESENT,
            "8": LIGHT_LEVEL_SENSOR_3,
            "9": TEMPERATURE_SENSOR_3,
        }
    )

    mock_bridge.mock_sensor_responses.append(new_sensor_response)

    # Force updates to run again
    await mock_bridge.sensor_manager.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 9

    presence = hass.states.get("binary_sensor.bedroom_sensor_motion")
    assert presence is not None
    assert presence.state == "on"
    temperature = hass.states.get("sensor.bedroom_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "17.75"


async def test_sensor_removed(hass, mock_bridge):
    """Test if 2nd update has removed sensor."""
    mock_bridge.mock_sensor_responses.append(SENSOR_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 6

    mock_bridge.mock_sensor_responses.clear()
    keys = ("1", "2", "3")
    mock_bridge.mock_sensor_responses.append({k: SENSOR_RESPONSE[k] for k in keys})

    # Force updates to run again
    await mock_bridge.sensor_manager.coordinator.async_refresh()

    # To flush out the service call to update the group
    await hass.async_block_till_done()

    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    sensor = hass.states.get("binary_sensor.living_room_sensor_motion")
    assert sensor is not None

    removed_sensor = hass.states.get("binary_sensor.kitchen_sensor_motion")
    assert removed_sensor is None


async def test_update_timeout(hass, mock_bridge):
    """Test bridge marked as not available if timeout error during update."""
    mock_bridge.api.sensors.update = Mock(side_effect=asyncio.TimeoutError)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0


async def test_update_unauthorized(hass, mock_bridge):
    """Test bridge marked as not authorized if unauthorized during update."""
    mock_bridge.api.sensors.update = Mock(side_effect=aiohue.Unauthorized)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0
    assert len(mock_bridge.handle_unauthorized_error.mock_calls) == 1
