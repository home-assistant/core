"""The tests for the MQTT room presence sensor."""
import datetime
import json
from unittest.mock import patch

from homeassistant.components.mqtt import CONF_QOS, CONF_STATE_TOPIC, DEFAULT_QOS
import homeassistant.components.sensor as sensor
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import async_fire_mqtt_message, async_mock_mqtt_component

DEVICE_ID = "123TESTMAC"
NAME = "test_device"
BEDROOM = "bedroom"
LIVING_ROOM = "living_room"

BEDROOM_TOPIC = f"room_presence/{BEDROOM}"
LIVING_ROOM_TOPIC = f"room_presence/{LIVING_ROOM}"

SENSOR_STATE = f"sensor.{NAME}"

CONF_DEVICE_ID = "device_id"
CONF_TIMEOUT = "timeout"

NEAR_MESSAGE = {"id": DEVICE_ID, "name": NAME, "distance": 1}

FAR_MESSAGE = {"id": DEVICE_ID, "name": NAME, "distance": 10}

REALLY_FAR_MESSAGE = {"id": DEVICE_ID, "name": NAME, "distance": 20}


async def send_message(hass, topic, message):
    """Test the sending of a message."""
    async_fire_mqtt_message(hass, topic, json.dumps(message))
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def assert_state(hass, room):
    """Test the assertion of a room state."""
    state = hass.states.get(SENSOR_STATE)
    assert state.state == room


async def assert_distance(hass, distance):
    """Test the assertion of a distance state."""
    state = hass.states.get(SENSOR_STATE)
    assert state.attributes.get("distance") == distance


async def test_room_update(hass):
    """Test the updating between rooms."""
    await async_mock_mqtt_component(hass)

    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                CONF_PLATFORM: "mqtt_room",
                CONF_NAME: NAME,
                CONF_DEVICE_ID: DEVICE_ID,
                CONF_STATE_TOPIC: "room_presence",
                CONF_QOS: DEFAULT_QOS,
                CONF_TIMEOUT: 5,
            }
        },
    )

    await send_message(hass, BEDROOM_TOPIC, FAR_MESSAGE)
    await assert_state(hass, BEDROOM)
    await assert_distance(hass, 10)

    await send_message(hass, LIVING_ROOM_TOPIC, NEAR_MESSAGE)
    await assert_state(hass, LIVING_ROOM)
    await assert_distance(hass, 1)

    await send_message(hass, BEDROOM_TOPIC, FAR_MESSAGE)
    await assert_state(hass, LIVING_ROOM)
    await assert_distance(hass, 1)

    time = dt.utcnow() + datetime.timedelta(seconds=7)
    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=time):
        await send_message(hass, BEDROOM_TOPIC, FAR_MESSAGE)
        await assert_state(hass, BEDROOM)
        await assert_distance(hass, 10)
