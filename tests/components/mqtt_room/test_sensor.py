"""The tests for the MQTT room presence sensor."""
import datetime
import json
from unittest.mock import patch

import pytest

from homeassistant.components.mqtt import CONF_QOS, CONF_STATE_TOPIC, DEFAULT_QOS
import homeassistant.components.sensor as sensor
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient

DEVICE_ID = "123TESTMAC"
NAME = "test_device"
BEDROOM = "bedroom"
LIVING_ROOM = "living_room"

BEDROOM_TOPIC = f"room_presence/{BEDROOM}"
LIVING_ROOM_TOPIC = f"room_presence/{LIVING_ROOM}"

SENSOR_STATE = f"sensor.{NAME}"

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


async def test_no_mqtt(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test no mqtt available."""
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
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_STATE)
    assert state is None
    assert "MQTT integration is not available" in caplog.text


async def test_room_update(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the updating between rooms."""
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
    await hass.async_block_till_done()

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


async def test_unique_id_is_set(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the updating between rooms."""
    unique_name = "my_unique_name_0123456789"
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
                CONF_UNIQUE_ID: unique_name,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_STATE)
    assert state.state is not None

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(SENSOR_STATE)
    assert entry.unique_id == unique_name
